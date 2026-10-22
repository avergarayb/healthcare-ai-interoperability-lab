"""Synthetic institutional guidance: parse, chunk, index, and retrieve.

FHIR remains the source of patient facts. Deterministic protocols remain the
source of operational evaluation. This module only retrieves repository-controlled
institutional text. It does not prove that arbitrary text is free of personal data.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.institutional_embeddings import (
    MAX_VECTOR_DIMENSION,
    EmbeddingUnavailable,
    GeminiEmbeddingProvider,
)
from app.institutional_knowledge_sqlite import (
    InstitutionalKnowledgeStoreError,
    SQLiteInstitutionalKnowledgeIndex,
)

log = logging.getLogger("ai-service")

RETRIEVAL_SCHEMA = "INSTITUTIONAL_KNOWLEDGE_RETRIEVAL_V1"
CONTENT_ROLE = "institutional_document_data"
SOURCE_TYPE = "synthetic_institutional_procedure"
LANGUAGE = "en"
BANNER = "Synthetic demonstration material. Not validated clinical guidance."
POST_CONSULTATION_RESULT_REVIEW_V1 = "POST_CONSULTATION_RESULT_REVIEW_V1"
MISSED_FOLLOW_UP_REVIEW_V1 = "MISSED_FOLLOW_UP_REVIEW_V1"
PROTOCOL_IDS = frozenset(
    {POST_CONSULTATION_RESULT_REVIEW_V1, MISSED_FOLLOW_UP_REVIEW_V1}
)
OPERATIONAL_REASON_CODES = frozenset(
    {
        "post_consultation_result_requires_review",
        "upcoming_confirmed_appointment",
        "appointment_classification_ambiguous",
        "finished_encounter_missing",
        "final_observation_missing",
        "explicit_encounter_association_missing",
        "encounter_end_missing_or_invalid",
        "observation_issued_missing_or_invalid",
        "observation_issued_before_encounter_end",
        "required_collection_not_read",
        "authorized_patient_missing",
        "acquisition_unavailable",
        "bounded_search_incomplete",
        "patient_resolution_incomplete",
        "patient_resolution_unavailable",
        "patient_resolution_invalid",
        "patient_read_unavailable",
        "encounter_acquisition_unavailable",
        "observation_acquisition_unavailable",
        "appointment_acquisition_unavailable",
        "appointment_integrity_failure",
        "appointment_search_incomplete",
        "missed_follow_up_without_confirmed_replacement",
        "confirmed_future_follow_up_exists",
        "eligible_past_noshow_absent",
        "appointment_start_missing_or_invalid",
    }
)
REQUIRED_SECTIONS = (
    "Purpose",
    "Scope",
    "Operational Trigger",
    "Review Procedure",
    "Human Authority",
    "Outcomes",
    "Non-goals",
)
MAX_CHUNK_CHARACTERS = 2000
MAX_FILE_BYTES = 32_768
MAX_DOCUMENTS = 16
MAX_QUERY_CHARACTERS = 400
MAX_TOP_K = 3
MAX_REASON_CODES = 8
CORPUS_ROOT = Path(__file__).resolve().parent.parent / "knowledge" / "institutional"
_API_REASONS = frozenset(
    {"index_not_ready", "embedding_unavailable", "vector_integrity", "model_mismatch"}
)
_DOCUMENT_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_VERSION = re.compile(r"^[0-9]+\.[0-9]+$")
_DATE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
_FILE_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*\.md$")
_HEX_HASH = re.compile(r"^[0-9a-f]{64}$")
_METADATA_KEYS = frozenset(
    {
        "documentId",
        "title",
        "version",
        "status",
        "effectiveDate",
        "sourceType",
        "synthetic",
        "protocolIds",
        "language",
    }
)
_FORBIDDEN_DOCUMENT_MARKERS = (
    "Patient/",
    "Encounter/",
    "Observation/",
    "Appointment/",
    "resourceType",
    "caseId",
)
_FORBIDDEN_QUERY_PARTS = (
    "patient/",
    "encounter/",
    "observation/",
    "appointment/",
    "resourcetype",
    "caseid",
    "reviewcase",
    "../",
    "..\\",
    "http://",
    "https://",
)
ProtocolId = Literal[
    "POST_CONSULTATION_RESULT_REVIEW_V1",
    "MISSED_FOLLOW_UP_REVIEW_V1",
]


class InstitutionalKnowledgeError(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True)
class KnowledgeChunk:
    document_id: str
    title: str
    version: str
    document_status: str
    section: str
    ordinal: int
    chunk_id: str
    content_hash: str
    language: str
    synthetic: bool
    text: str


@dataclass(frozen=True)
class InstitutionalDocument:
    document_id: str
    title: str
    version: str
    status: str
    effective_date: str
    source_type: str
    synthetic: bool
    protocol_ids: tuple[str, ...]
    language: str
    content_hash: str
    chunks: tuple[KnowledgeChunk, ...]


@dataclass(frozen=True)
class IndexedChunk:
    document_id: str
    title: str
    version: str
    document_status: str
    section: str
    ordinal: int
    chunk_id: str
    content_hash: str
    language: str
    synthetic: bool
    text: str
    protocol_ids: tuple[str, ...]
    embedding_model: str
    vector: tuple[float, ...]


@dataclass(frozen=True)
class RetrievedChunk:
    document_id: str
    title: str
    version: str
    document_status: str
    section: str
    ordinal: int
    chunk_id: str
    content_hash: str
    language: str
    synthetic: bool
    score: float
    text: str

    def as_dict(self) -> dict[str, object]:
        return {
            "documentId": self.document_id,
            "title": self.title,
            "version": self.version,
            "documentStatus": self.document_status,
            "section": self.section,
            "ordinal": self.ordinal,
            "chunkId": self.chunk_id,
            "contentHash": self.content_hash,
            "language": self.language,
            "synthetic": self.synthetic,
            "score": self.score,
            "text": self.text,
            "contentRole": CONTENT_ROLE,
        }


@dataclass(frozen=True)
class RetrievalResult:
    status: str
    protocol_id: str
    chunks: tuple[RetrievedChunk, ...] = ()
    reason: str | None = None

    def as_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "schema": RETRIEVAL_SCHEMA,
            "status": self.status,
            "protocolId": self.protocol_id,
            "chunks": [chunk.as_dict() for chunk in self.chunks],
        }
        if self.reason is not None:
            payload["reason"] = self.reason
        return payload


class KnowledgeRetrieveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocolId: ProtocolId
    queryText: str
    reasonCodes: list[str] | None = Field(default=None, max_length=MAX_REASON_CODES)
    version: str | None = None
    topK: int = Field(default=MAX_TOP_K, ge=1, le=MAX_TOP_K)

    @field_validator("queryText")
    @classmethod
    def _query_text(cls, value: str) -> str:
        if not isinstance(value, str) or len(value) > MAX_QUERY_CHARACTERS:
            raise ValueError("queryText is invalid")
        stripped = value.strip()
        if not stripped or len(stripped) > MAX_QUERY_CHARACTERS:
            raise ValueError("queryText is invalid")
        lowered = stripped.casefold()
        if any(part in lowered for part in _FORBIDDEN_QUERY_PARTS):
            raise ValueError("queryText is invalid")
        return stripped

    @field_validator("reasonCodes")
    @classmethod
    def _reason_codes(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        if not value or len(value) > MAX_REASON_CODES or len(set(value)) != len(value):
            raise ValueError("reasonCodes are invalid")
        if any(code not in OPERATIONAL_REASON_CODES for code in value):
            raise ValueError("reasonCodes are invalid")
        return value

    @field_validator("version")
    @classmethod
    def _version(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if _VERSION.fullmatch(value) is None:
            raise ValueError("version is invalid")
        return value


class _UnconfiguredEmbeddingProvider:
    def __init__(self, model: str) -> None:
        self._model = model or "unconfigured"

    @property
    def model_id(self) -> str:
        return self._model

    def embed_texts(self, texts: Sequence[str]) -> list[tuple[float, ...]]:
        raise EmbeddingUnavailable()


class UnavailableInstitutionalKnowledge:
    def retrieve(self, request: KnowledgeRetrieveRequest) -> RetrievalResult:
        return _unavailable(request.protocolId, "index_not_ready")


class InstitutionalKnowledgeIndex:
    def __init__(self, store: SQLiteInstitutionalKnowledgeIndex, embedder, min_score: float) -> None:
        self._store = store
        self._embedder = embedder
        self._min_score = min_score

    def retrieve(self, request: KnowledgeRetrieveRequest) -> RetrievalResult:
        protocol_id = request.protocolId
        try:
            state = self._store.read_state()
        except InstitutionalKnowledgeStoreError:
            return _unavailable(protocol_id, "index_not_ready")
        if not state.ready:
            return _unavailable(protocol_id, "index_not_ready")
        if state.embedding_model != self._embedder.model_id:
            return _unavailable(protocol_id, "model_mismatch")
        try:
            candidates = _validated_candidates(self._store.fetch_rows(), state.embedding_model, state.vector_dimension)
        except InstitutionalKnowledgeError:
            return _unavailable(protocol_id, "vector_integrity")
        except InstitutionalKnowledgeStoreError:
            return _unavailable(protocol_id, "vector_integrity")
        selected = [
            candidate
            for candidate in candidates
            if protocol_id in candidate.protocol_ids
            and (candidate.version == request.version if request.version else candidate.document_status == "active")
        ]
        try:
            query_vectors = self._embedder.embed_texts([request.queryText])
        except EmbeddingUnavailable:
            return _unavailable(protocol_id, "embedding_unavailable")
        except Exception:
            return _unavailable(protocol_id, "embedding_unavailable")
        if len(query_vectors) != 1:
            return _unavailable(protocol_id, "embedding_unavailable")
        try:
            validate_vector(query_vectors[0])
            if len(query_vectors[0]) != state.vector_dimension:
                return _unavailable(protocol_id, "vector_integrity")
            scored = [
                (cosine_similarity(query_vectors[0], candidate.vector), candidate)
                for candidate in selected
            ]
        except InstitutionalKnowledgeError:
            return _unavailable(protocol_id, "vector_integrity")
        eligible = [item for item in scored if item[0] >= self._min_score]
        eligible.sort(key=lambda item: (-item[0], item[1].chunk_id))
        chosen = eligible[: request.topK]
        if not chosen:
            return RetrievalResult(status="NO_RELEVANT_GUIDANCE", protocol_id=protocol_id)
        return RetrievalResult(
            status="FOUND",
            protocol_id=protocol_id,
            chunks=tuple(_retrieved(candidate, score) for score, candidate in chosen),
        )


def attach_institutional_knowledge(application, settings, *, embedder=None, corpus_root: Path | None = None) -> None:
    try:
        application.state.institutional_knowledge = open_institutional_knowledge(
            settings,
            embedder=embedder,
            corpus_root=corpus_root,
        )
    except Exception:
        log.info("knowledge_index status=UNAVAILABLE reason=index_not_ready")
        application.state.institutional_knowledge = UnavailableInstitutionalKnowledge()


def open_institutional_knowledge(settings, *, embedder=None, corpus_root: Path | None = None):
    store = SQLiteInstitutionalKnowledgeIndex(settings.institutional_knowledge_db_path)
    store.initialize()
    try:
        documents = load_corpus(corpus_root or CORPUS_ROOT)
    except InstitutionalKnowledgeError as exc:
        store.mark_unavailable()
        log.info("knowledge_index status=UNAVAILABLE reason=%s", exc.reason)
        return InstitutionalKnowledgeIndex(
            store,
            embedder or _UnconfiguredEmbeddingProvider(settings.institutional_knowledge_embedding_model),
            settings.institutional_knowledge_min_score,
        )
    if embedder is None:
        try:
            embedder = GeminiEmbeddingProvider(
                api_key=settings.gemini_api_key,
                model=settings.institutional_knowledge_embedding_model,
            )
        except EmbeddingUnavailable:
            store.mark_unavailable()
            log.info("knowledge_index status=UNAVAILABLE reason=embedding_unavailable")
            return InstitutionalKnowledgeIndex(
                store,
                _UnconfiguredEmbeddingProvider(settings.institutional_knowledge_embedding_model),
                settings.institutional_knowledge_min_score,
            )
    try:
        rebuild_index(store, documents, embedder)
    except InstitutionalKnowledgeError as exc:
        store.mark_unavailable()
        log.info("knowledge_index status=UNAVAILABLE reason=%s", exc.reason)
    except EmbeddingUnavailable:
        store.mark_unavailable()
        log.info("knowledge_index status=UNAVAILABLE reason=embedding_unavailable")
    except InstitutionalKnowledgeStoreError as exc:
        store.mark_unavailable()
        log.info("knowledge_index status=UNAVAILABLE reason=%s", exc.reason)
    return InstitutionalKnowledgeIndex(store, embedder, settings.institutional_knowledge_min_score)


def load_corpus(corpus_root: Path) -> tuple[InstitutionalDocument, ...]:
    root = corpus_root.resolve()
    if not root.is_dir():
        raise InstitutionalKnowledgeError("corpus_invalid")
    entries = sorted(root.iterdir(), key=lambda item: item.name)
    if not entries or len(entries) > MAX_DOCUMENTS:
        raise InstitutionalKnowledgeError("corpus_invalid")
    documents: list[InstitutionalDocument] = []
    for path in entries:
        if not path.is_file() or path.suffix != ".md" or _FILE_NAME.fullmatch(path.name) is None:
            raise InstitutionalKnowledgeError("corpus_invalid")
        resolved = path.resolve()
        if resolved.parent != root:
            raise InstitutionalKnowledgeError("corpus_invalid")
        data = path.read_bytes()
        if len(data) > MAX_FILE_BYTES or b"\x00" in data:
            raise InstitutionalKnowledgeError("corpus_invalid")
        try:
            text = data.decode("utf-8")
        except UnicodeError as exc:
            raise InstitutionalKnowledgeError("corpus_invalid") from exc
        documents.append(parse_institutional_document(text))
    validate_corpus(documents)
    return tuple(documents)


def validate_corpus(documents: Sequence[InstitutionalDocument]) -> None:
    if not documents or len(documents) > MAX_DOCUMENTS:
        raise InstitutionalKnowledgeError("corpus_invalid")
    identities: set[tuple[str, str]] = set()
    active: dict[str, str] = {}
    chunk_ids: set[str] = set()
    for document in documents:
        identity = (document.document_id, document.version)
        if identity in identities:
            raise InstitutionalKnowledgeError("duplicate_identity")
        identities.add(identity)
        if document.status == "active":
            if document.document_id in active:
                raise InstitutionalKnowledgeError("active_version_conflict")
            active[document.document_id] = document.version
        for chunk in document.chunks:
            if chunk.chunk_id in chunk_ids:
                raise InstitutionalKnowledgeError("duplicate_identity")
            chunk_ids.add(chunk.chunk_id)


def parse_institutional_document(raw: str) -> InstitutionalDocument:
    if "\x00" in raw:
        raise InstitutionalKnowledgeError("corpus_invalid")
    normalized = raw.replace("\r\n", "\n").replace("\r", "\n")
    if not normalized.startswith("```json\n"):
        raise InstitutionalKnowledgeError("metadata_invalid")
    fence = normalized.find("\n```\n", len("```json\n"))
    if fence < 0:
        raise InstitutionalKnowledgeError("metadata_invalid")
    metadata = _parse_metadata(normalized[len("```json\n") : fence])
    body = _normalize_body(normalized[fence + len("\n```\n") :])
    for marker in _FORBIDDEN_DOCUMENT_MARKERS:
        if marker in body:
            raise InstitutionalKnowledgeError("corpus_invalid")
    content_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
    chunks = _chunk_document(body, metadata, content_hash)
    return InstitutionalDocument(
        document_id=metadata["documentId"],
        title=metadata["title"],
        version=metadata["version"],
        status=metadata["status"],
        effective_date=metadata["effectiveDate"],
        source_type=metadata["sourceType"],
        synthetic=True,
        protocol_ids=metadata["protocolIds"],
        language=LANGUAGE,
        content_hash=content_hash,
        chunks=chunks,
    )


def rebuild_index(store, documents: Sequence[InstitutionalDocument], embedder) -> None:
    try:
        validate_corpus(documents)
    except InstitutionalKnowledgeError:
        store.mark_unavailable()
        raise
    chunks = tuple(chunk for document in documents for chunk in document.chunks)
    state_model = ""
    try:
        state_model = store.read_state().embedding_model
    except InstitutionalKnowledgeStoreError:
        state_model = ""
    cached = store.reusable_vectors(embedder.model_id) if state_model == embedder.model_id else {}
    store.mark_unavailable()
    vectors: dict[str, tuple[float, ...]] = {}
    pending: list[KnowledgeChunk] = []
    for chunk in chunks:
        cached_item = cached.get(chunk.chunk_id)
        if cached_item is not None and cached_item[0] == chunk.content_hash:
            try:
                validate_vector(cached_item[1])
            except InstitutionalKnowledgeError:
                pending.append(chunk)
            else:
                vectors[chunk.chunk_id] = cached_item[1]
        else:
            pending.append(chunk)
    try:
        if pending:
            embedded = embedder.embed_texts([chunk.text for chunk in pending])
            if len(embedded) != len(pending):
                raise EmbeddingUnavailable()
            for chunk, vector in zip(pending, embedded):
                validate_vector(vector)
                vectors[chunk.chunk_id] = vector
        dimensions = {len(vector) for vector in vectors.values()}
        if len(dimensions) != 1 or set(vectors) != {chunk.chunk_id for chunk in chunks}:
            raise InstitutionalKnowledgeError("vector_integrity")
        store.publish(documents, chunks, vectors, embedder.model_id, _fingerprint(documents))
    except InstitutionalKnowledgeError:
        store.mark_unavailable()
        raise
    except EmbeddingUnavailable:
        store.mark_unavailable()
        raise
    except InstitutionalKnowledgeStoreError:
        store.mark_unavailable()
        raise
    except Exception:
        store.mark_unavailable()
        raise EmbeddingUnavailable() from None
    log.info(
        "knowledge_index status=READY documents=%s chunks=%s embedded=%s embeddingModel=%s",
        len(documents),
        len(chunks),
        len(pending),
        embedder.model_id,
    )


def chunk_id_for(*, document_id: str, version: str, section: str, ordinal: int, content_hash: str) -> str:
    payload = {
        "contentHash": content_hash,
        "documentId": document_id,
        "ordinal": ordinal,
        "section": section,
        "version": version,
    }
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or not left:
        raise InstitutionalKnowledgeError("vector_integrity")
    dot = 0.0
    left_norm = 0.0
    right_norm = 0.0
    for left_value, right_value in zip(left, right):
        if not math.isfinite(left_value) or not math.isfinite(right_value):
            raise InstitutionalKnowledgeError("vector_integrity")
        dot += left_value * right_value
        left_norm += left_value * left_value
        right_norm += right_value * right_value
    if left_norm == 0.0 or right_norm == 0.0:
        raise InstitutionalKnowledgeError("vector_integrity")
    score = dot / math.sqrt(left_norm * right_norm)
    if not math.isfinite(score):
        raise InstitutionalKnowledgeError("vector_integrity")
    if score > 1.0:
        return 1.0
    if score < -1.0:
        return -1.0
    return score


def validate_vector(vector: object) -> None:
    if not isinstance(vector, tuple) or not 1 <= len(vector) <= MAX_VECTOR_DIMENSION:
        raise InstitutionalKnowledgeError("vector_integrity")
    for value in vector:
        if isinstance(value, bool) or not isinstance(value, float) or not math.isfinite(value):
            raise InstitutionalKnowledgeError("vector_integrity")


def _normalize_body(body: str) -> str:
    lines = [line.rstrip(" \t") for line in body.split("\n")]
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines) + "\n"


def _metadata_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    parsed: dict[str, object] = {}
    for key, item in pairs:
        if key in parsed:
            raise InstitutionalKnowledgeError("metadata_invalid")
        parsed[key] = item
    return parsed


def _parse_metadata(raw_json: str) -> dict[str, object]:
    try:
        value = json.loads(raw_json, object_pairs_hook=_metadata_object)
    except json.JSONDecodeError as exc:
        raise InstitutionalKnowledgeError("metadata_invalid") from exc
    if not isinstance(value, dict) or set(value) != _METADATA_KEYS:
        raise InstitutionalKnowledgeError("metadata_invalid")
    document_id = value["documentId"]
    title = value["title"]
    version = value["version"]
    status = value["status"]
    effective_date = value["effectiveDate"]
    source_type = value["sourceType"]
    synthetic = value["synthetic"]
    protocol_ids = value["protocolIds"]
    language = value["language"]
    if (
        not isinstance(document_id, str)
        or _DOCUMENT_ID.fullmatch(document_id) is None
        or len(document_id) > 80
        or not isinstance(title, str)
        or not 1 <= len(title) <= 160
        or "\n" in title
        or not isinstance(version, str)
        or _VERSION.fullmatch(version) is None
        or status not in {"active", "superseded"}
        or not isinstance(effective_date, str)
        or _DATE.fullmatch(effective_date) is None
        or source_type != SOURCE_TYPE
        or synthetic is not True
        or language != LANGUAGE
        or not isinstance(protocol_ids, list)
        or not 1 <= len(protocol_ids) <= len(PROTOCOL_IDS)
        or len(set(protocol_ids)) != len(protocol_ids)
        or any(protocol_id not in PROTOCOL_IDS for protocol_id in protocol_ids)
    ):
        raise InstitutionalKnowledgeError("metadata_invalid")
    try:
        date.fromisoformat(effective_date)
    except ValueError as exc:
        raise InstitutionalKnowledgeError("metadata_invalid") from exc
    return {
        "documentId": document_id,
        "title": title,
        "version": version,
        "status": status,
        "effectiveDate": effective_date,
        "sourceType": source_type,
        "protocolIds": tuple(protocol_ids),
    }


def _chunk_document(body: str, metadata: dict[str, object], document_hash: str) -> tuple[KnowledgeChunk, ...]:
    del document_hash
    lines = body.split("\n")
    title = str(metadata["title"])
    if not lines or lines[0] != f"# {title}":
        raise InstitutionalKnowledgeError("section_invalid")
    index = 1
    while index < len(lines) and lines[index] == "":
        index += 1
    if index >= len(lines) or lines[index] != BANNER:
        raise InstitutionalKnowledgeError("section_invalid")
    index += 1
    sections: list[tuple[str, str]] = []
    for expected in REQUIRED_SECTIONS:
        while index < len(lines) and lines[index] == "":
            index += 1
        if index >= len(lines) or lines[index] != f"## {expected}":
            raise InstitutionalKnowledgeError("section_invalid")
        index += 1
        start = index
        while index < len(lines) and not lines[index].startswith("## "):
            if lines[index].startswith("#"):
                raise InstitutionalKnowledgeError("section_invalid")
            index += 1
        text = "\n".join(lines[start:index]).strip("\n").strip()
        if text == "":
            raise InstitutionalKnowledgeError("section_invalid")
        sections.append((expected, text))
    while index < len(lines) and lines[index] == "":
        index += 1
    if index != len(lines):
        raise InstitutionalKnowledgeError("section_invalid")
    chunks: list[KnowledgeChunk] = []
    ordinal = 0
    for section, text in sections:
        for part in _split_section(text):
            content_hash = hashlib.sha256(part.encode("utf-8")).hexdigest()
            chunks.append(
                KnowledgeChunk(
                    document_id=str(metadata["documentId"]),
                    title=title,
                    version=str(metadata["version"]),
                    document_status=str(metadata["status"]),
                    section=section,
                    ordinal=ordinal,
                    chunk_id=chunk_id_for(
                        document_id=str(metadata["documentId"]),
                        version=str(metadata["version"]),
                        section=section,
                        ordinal=ordinal,
                        content_hash=content_hash,
                    ),
                    content_hash=content_hash,
                    language=LANGUAGE,
                    synthetic=True,
                    text=part,
                )
            )
            ordinal += 1
    if not chunks or len(chunks) > 32:
        raise InstitutionalKnowledgeError("section_invalid")
    return tuple(chunks)


def _split_section(text: str) -> list[str]:
    if len(text) <= MAX_CHUNK_CHARACTERS:
        return [text]
    paragraphs = [part for part in text.split("\n\n") if part.strip() != ""]
    if len(paragraphs) <= 1:
        raise InstitutionalKnowledgeError("section_invalid")
    parts: list[str] = []
    current: list[str] = []
    current_length = 0
    for paragraph in paragraphs:
        if len(paragraph) > MAX_CHUNK_CHARACTERS:
            raise InstitutionalKnowledgeError("section_invalid")
        addition = len(paragraph) if not current else 2 + len(paragraph)
        if current and current_length + addition > MAX_CHUNK_CHARACTERS:
            parts.append("\n\n".join(current))
            current = [paragraph]
            current_length = len(paragraph)
        else:
            current.append(paragraph)
            current_length += addition
    if current:
        parts.append("\n\n".join(current))
    if any(len(part) > MAX_CHUNK_CHARACTERS or part == "" for part in parts):
        raise InstitutionalKnowledgeError("section_invalid")
    return parts


def _validated_candidates(rows: Sequence[dict[str, object]], embedding_model: str, dimension: int) -> tuple[IndexedChunk, ...]:
    candidates: list[IndexedChunk] = []
    active: dict[str, str] = {}
    seen: set[str] = set()
    for row in rows:
        text = row["text"]
        content_hash = row["content_hash"]
        chunk_id = row["chunk_id"]
        document_id = row["document_id"]
        version = row["version"]
        section = row["section"]
        ordinal = row["ordinal"]
        if (
            not isinstance(text, str)
            or not isinstance(content_hash, str)
            or not isinstance(chunk_id, str)
            or not isinstance(document_id, str)
            or not isinstance(version, str)
            or not isinstance(section, str)
            or isinstance(ordinal, bool)
            or not isinstance(ordinal, int)
            or text == ""
            or len(text) > MAX_CHUNK_CHARACTERS
            or _HEX_HASH.fullmatch(content_hash) is None
            or _HEX_HASH.fullmatch(chunk_id) is None
            or hashlib.sha256(text.encode("utf-8")).hexdigest() != content_hash
            or row["language"] != LANGUAGE
            or int(row["synthetic"]) != 1
            or int(row["document_synthetic"]) != 1
            or row["document_status"] not in {"active", "superseded"}
            or row["document_row_status"] != row["document_status"]
            or row["embedding_model"] != embedding_model
        ):
            raise InstitutionalKnowledgeError("vector_integrity")
        vector = _vector_from_row(row["vector_json"])
        if len(vector) != dimension or int(row["dimension"]) != dimension:
            raise InstitutionalKnowledgeError("vector_integrity")
        validate_vector(vector)
        expected_id = chunk_id_for(
            document_id=document_id,
            version=version,
            section=section,
            ordinal=ordinal,
            content_hash=content_hash,
        )
        if expected_id != chunk_id or chunk_id in seen:
            raise InstitutionalKnowledgeError("vector_integrity")
        seen.add(chunk_id)
        protocol_ids = _protocol_ids(row["protocol_ids_json"])
        status = str(row["document_status"])
        if status == "active":
            previous = active.get(document_id)
            if previous is not None and previous != version:
                raise InstitutionalKnowledgeError("vector_integrity")
            active[document_id] = version
        candidates.append(
            IndexedChunk(
                document_id=document_id,
                title=str(row["title"]),
                version=version,
                document_status=status,
                section=section,
                ordinal=ordinal,
                chunk_id=chunk_id,
                content_hash=content_hash,
                language=LANGUAGE,
                synthetic=True,
                text=text,
                protocol_ids=protocol_ids,
                embedding_model=embedding_model,
                vector=vector,
            )
        )
    return tuple(candidates)


def _protocol_ids(raw: object) -> tuple[str, ...]:
    if not isinstance(raw, str):
        raise InstitutionalKnowledgeError("vector_integrity")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise InstitutionalKnowledgeError("vector_integrity") from exc
    if (
        not isinstance(parsed, list)
        or not parsed
        or len(set(parsed)) != len(parsed)
        or any(item not in PROTOCOL_IDS for item in parsed)
    ):
        raise InstitutionalKnowledgeError("vector_integrity")
    return tuple(parsed)


def _vector_from_row(raw: object) -> tuple[float, ...]:
    if not isinstance(raw, str):
        raise InstitutionalKnowledgeError("vector_integrity")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise InstitutionalKnowledgeError("vector_integrity") from exc
    if not isinstance(parsed, list) or not parsed:
        raise InstitutionalKnowledgeError("vector_integrity")
    values: list[float] = []
    for item in parsed:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise InstitutionalKnowledgeError("vector_integrity")
        value = float(item)
        if not math.isfinite(value):
            raise InstitutionalKnowledgeError("vector_integrity")
        values.append(value)
    return tuple(values)


def _retrieved(candidate: IndexedChunk, score: float) -> RetrievedChunk:
    return RetrievedChunk(
        document_id=candidate.document_id,
        title=candidate.title,
        version=candidate.version,
        document_status=candidate.document_status,
        section=candidate.section,
        ordinal=candidate.ordinal,
        chunk_id=candidate.chunk_id,
        content_hash=candidate.content_hash,
        language=candidate.language,
        synthetic=candidate.synthetic,
        score=score,
        text=candidate.text,
    )


def _fingerprint(documents: Sequence[InstitutionalDocument]) -> str:
    payload = [
        {"contentHash": document.content_hash, "documentId": document.document_id, "version": document.version}
        for document in sorted(documents, key=lambda item: (item.document_id, item.version))
    ]
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _unavailable(protocol_id: str, reason: str) -> RetrievalResult:
    if reason not in _API_REASONS:
        reason = "index_not_ready"
    return RetrievalResult(status="UNAVAILABLE", protocol_id=protocol_id, reason=reason)
