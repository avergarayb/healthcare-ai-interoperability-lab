from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.followup_review_sqlite import SQLiteFollowUpReviewCaseRepository
from app.institutional_embeddings import EmbeddingUnavailable, GeminiEmbeddingProvider
from app.institutional_knowledge import (
    BANNER,
    CORPUS_ROOT,
    MAX_CHUNK_CHARACTERS,
    MISSED_FOLLOW_UP_REVIEW_V1,
    POST_CONSULTATION_RESULT_REVIEW_V1,
    InstitutionalDocument,
    InstitutionalKnowledgeError,
    KnowledgeChunk,
    KnowledgeRetrieveRequest,
    attach_institutional_knowledge,
    chunk_id_for,
    load_corpus,
    open_institutional_knowledge,
    parse_institutional_document,
    rebuild_index,
)
from app.institutional_knowledge_sqlite import (
    SQLiteInstitutionalKnowledgeIndex,
)
from app.human_session_sqlite import SQLiteHumanSessionRepository
from app.main import app, get_settings
from app.post_consultation_review import evaluate_post_consultation_review
from app.missed_follow_up_review import evaluate_missed_follow_up

TOKEN = "test-model-boundary-token"
AUTH = {"X-Service-Token": TOKEN}
SECTIONS = (
    "Purpose",
    "Scope",
    "Operational Trigger",
    "Review Procedure",
    "Human Authority",
    "Outcomes",
    "Non-goals",
)
CARE_Y = math.sqrt(1.0 - 0.81)
POST_VECTOR = (0.8, 0.6)
CARE_VECTOR = (0.9, CARE_Y)
MISSED_VECTOR = (1.0, 0.0)


class CountingEmbedder:
    def __init__(self, model_id: str = "deterministic-fake-v1") -> None:
        self.model_id = model_id
        self.calls: list[list[str]] = []

    def embed_texts(self, texts):
        self.calls.append(list(texts))
        return [self._vector(text) for text in texts]

    def _vector(self, text: str) -> tuple[float, ...]:
        if text == "query-post":
            return (1.0, 0.0)
        if text == "query-missed":
            return POST_VECTOR
        if text == "query-low":
            return (0.0, 1.0)
        first = text.splitlines()[0]
        if first.startswith("vector:"):
            return tuple(float(item) for item in first.split(":", 1)[1].split(","))
        return (1.0, 0.0)


def _markdown(
    *,
    document_id: str,
    title: str,
    protocols: list[str],
    version: str = "1.0",
    status: str = "active",
    sections: dict[str, str] | None = None,
    synthetic: bool = True,
    source_type: str = "synthetic_institutional_procedure",
    language: str = "en",
    extra: dict | None = None,
    drop: str | None = None,
) -> str:
    metadata = {
        "documentId": document_id,
        "title": title,
        "version": version,
        "status": status,
        "effectiveDate": "2026-10-06",
        "sourceType": source_type,
        "synthetic": synthetic,
        "protocolIds": protocols,
        "language": language,
    }
    if extra:
        metadata.update(extra)
    if drop:
        metadata.pop(drop)
    chosen = sections or {name: f"{name} operational text for {document_id}." for name in SECTIONS}
    lines = [f"# {title}", "", BANNER, ""]
    for name in SECTIONS:
        lines.extend([f"## {name}", "", chosen[name], ""])
    return "```json\n" + json.dumps(metadata, indent=2) + "\n```\n" + "\n".join(lines).rstrip() + "\n"


def _write_corpus(directory: Path, files: dict[str, str]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (directory / name).write_text(text, encoding="utf-8")
    return directory


def _vector_sections(vector: tuple[float, ...], label: str) -> dict[str, str]:
    rendered = "vector:" + ",".join(str(value) for value in vector)
    return {name: f"{rendered}\n{label} {name} operational procedure." for name in SECTIONS}


def _configured(settings: Settings, tmp_path: Path, **changes) -> Settings:
    values = {
        "model_boundary_base_url": settings.model_boundary_base_url,
        "model_boundary_path": settings.model_boundary_path,
        "model_boundary_timeout_seconds": settings.model_boundary_timeout_seconds,
        "model_boundary_service_token": settings.model_boundary_service_token,
        "host": settings.host,
        "port": settings.port,
        "institutional_knowledge_db_path": str(tmp_path / "institutional-knowledge.sqlite3"),
        "institutional_knowledge_embedding_model": "deterministic-fake-v1",
        "institutional_knowledge_min_score": 0.68,
    }
    values.update(changes)
    return Settings(**values)


def _open(settings: Settings, tmp_path: Path, corpus: Path, embedder, **changes):
    configured = _configured(settings, tmp_path, **changes)
    return open_institutional_knowledge(configured, embedder=embedder, corpus_root=corpus), configured


def _request(protocol: str = POST_CONSULTATION_RESULT_REVIEW_V1, query: str = "query-post", **changes):
    payload = {"protocolId": protocol, "queryText": query}
    payload.update(changes)
    return KnowledgeRetrieveRequest.model_validate(payload)


def _normalized_body(raw: str) -> str:
    normalized = raw.replace("\r\n", "\n").replace("\r", "\n")
    fence = normalized.find("\n```\n", len("```json\n"))
    body = normalized[fence + len("\n```\n") :]
    lines = [line.rstrip(" \t") for line in body.split("\n")]
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines) + "\n"


def test_repository_corpus_is_the_closed_synthetic_set():
    documents = load_corpus(CORPUS_ROOT)
    by_id = {document.document_id: document for document in documents}
    assert set(by_id) == {
        "post-consultation-results-follow-up",
        "missed-follow-up-management",
        "care-coordination-procedures",
    }
    assert by_id["post-consultation-results-follow-up"].protocol_ids == (POST_CONSULTATION_RESULT_REVIEW_V1,)
    assert by_id["missed-follow-up-management"].protocol_ids == (MISSED_FOLLOW_UP_REVIEW_V1,)
    assert by_id["care-coordination-procedures"].protocol_ids == (
        POST_CONSULTATION_RESULT_REVIEW_V1,
        MISSED_FOLLOW_UP_REVIEW_V1,
    )
    for document in documents:
        assert document.version == "1.0"
        assert document.status == "active"
        assert document.language == "en"
        assert document.synthetic is True
        assert document.source_type == "synthetic_institutional_procedure"
        assert [chunk.section for chunk in document.chunks] == list(SECTIONS)
        assert [chunk.ordinal for chunk in document.chunks] == list(range(7))
        assert all(chunk.synthetic is True and chunk.language == "en" for chunk in document.chunks)
        assert BANNER not in "\n".join(chunk.text for chunk in document.chunks)
    care_trigger = next(
        chunk.text
        for chunk in by_id["care-coordination-procedures"].chunks
        if chunk.section == "Operational Trigger"
    )
    assert "no separate detection trigger" in care_trigger
    for path in CORPUS_ROOT.glob("*.md"):
        text = path.read_text(encoding="utf-8")
        assert text.count(BANNER) == 1
        lowered = text.casefold()
        for forbidden in ("diagnosis", "treatment", "medication", "severity", "urgency", "abnormal"):
            assert forbidden not in lowered
        for marker in ("Patient/", "Encounter/", "Observation/", "Appointment/", "caseId", "resourceType"):
            assert marker not in text


def test_duplicate_metadata_key_is_rejected_and_unique_metadata_is_unchanged():
    valid = _markdown(
        document_id="post-consultation-results-follow-up",
        title="Post-Consultation Results Follow-up Protocol",
        protocols=[POST_CONSULTATION_RESULT_REVIEW_V1],
    )
    parsed = parse_institutional_document(valid)
    again = parse_institutional_document(valid)
    assert again.content_hash == parsed.content_hash
    assert [chunk.chunk_id for chunk in again.chunks] == [chunk.chunk_id for chunk in parsed.chunks]
    assert parsed.synthetic is True
    duplicate = valid.replace('"synthetic": true', '"synthetic": false, "synthetic": true', 1)
    with pytest.raises(InstitutionalKnowledgeError) as rejected:
        parse_institutional_document(duplicate)
    assert rejected.value.reason == "metadata_invalid"


def test_metadata_source_language_and_protocol_allowlist_fail_closed():
    valid = _markdown(
        document_id="post-consultation-results-follow-up",
        title="Post-Consultation Results Follow-up Protocol",
        protocols=[POST_CONSULTATION_RESULT_REVIEW_V1],
    )
    parsed = parse_institutional_document(valid.replace("\n", "\r\n"))
    assert parsed.content_hash == hashlib.sha256(_normalized_body(valid).encode("utf-8")).hexdigest()
    again = parse_institutional_document(valid)
    assert [chunk.chunk_id for chunk in parsed.chunks] == [chunk.chunk_id for chunk in again.chunks]
    chunk = parsed.chunks[0]
    identity = {
        "contentHash": chunk.content_hash,
        "documentId": chunk.document_id,
        "ordinal": chunk.ordinal,
        "section": chunk.section,
        "version": chunk.version,
    }
    encoded = json.dumps(identity, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    assert chunk.chunk_id == hashlib.sha256(encoded).hexdigest()
    assert chunk.chunk_id == chunk_id_for(
        document_id=chunk.document_id,
        version=chunk.version,
        section=chunk.section,
        ordinal=chunk.ordinal,
        content_hash=chunk.content_hash,
    )
    changed = valid.replace("operational text", "changed operational text")
    assert parse_institutional_document(changed).content_hash != parsed.content_hash
    for broken in (
        valid.replace('"synthetic": true', '"synthetic": false'),
        valid.replace("synthetic_institutional_procedure", "uploaded_procedure"),
        valid.replace('"language": "en"', '"language": "es"'),
        valid.replace(POST_CONSULTATION_RESULT_REVIEW_V1, "OTHER_PROTOCOL"),
        valid.replace('"status": "active"', '"status": "current"'),
    ):
        with pytest.raises(InstitutionalKnowledgeError):
            parse_institutional_document(broken)
    with pytest.raises(InstitutionalKnowledgeError) as extra:
        parse_institutional_document(
            _markdown(
                document_id="post-consultation-results-follow-up",
                title="Post-Consultation Results Follow-up Protocol",
                protocols=[POST_CONSULTATION_RESULT_REVIEW_V1],
                extra={"caseId": "SYN-FOLLOWUP-001"},
            )
        )
    assert extra.value.reason == "metadata_invalid"


def test_empty_invalid_and_oversized_sections_fail_or_split_without_overlap():
    base = dict(
        document_id="post-consultation-results-follow-up",
        title="Post-Consultation Results Follow-up Protocol",
        protocols=[POST_CONSULTATION_RESULT_REVIEW_V1],
    )
    empty = {name: f"{name} operational text." for name in SECTIONS}
    empty["Purpose"] = "   "
    with pytest.raises(InstitutionalKnowledgeError) as missing:
        parse_institutional_document(_markdown(**base, sections=empty))
    assert missing.value.reason == "section_invalid"
    huge = {name: f"{name} operational text." for name in SECTIONS}
    huge["Purpose"] = "A" * (MAX_CHUNK_CHARACTERS + 1)
    with pytest.raises(InstitutionalKnowledgeError):
        parse_institutional_document(_markdown(**base, sections=huge))
    split = {name: f"{name} operational text." for name in SECTIONS}
    split["Purpose"] = ("A" * 1500) + "\n\n" + ("B" * 1500)
    document = parse_institutional_document(_markdown(**base, sections=split))
    assert document.chunks[0].section == "Purpose"
    assert document.chunks[1].section == "Purpose"
    assert document.chunks[0].ordinal == 0
    assert document.chunks[1].ordinal == 1
    assert document.chunks[2].ordinal == 2
    assert set(document.chunks[0].text) == {"A"}
    assert set(document.chunks[1].text) == {"B"}
    within = {name: f"{name} operational text." for name in SECTIONS}
    within["Purpose"] = "C" * MAX_CHUNK_CHARACTERS
    fitted = parse_institutional_document(_markdown(**base, sections=within))
    assert fitted.chunks[0].text == "C" * MAX_CHUNK_CHARACTERS
    assert fitted.chunks[1].section == "Scope"


def test_duplicate_chunk_identity_and_duplicate_active_versions_fail_closed(tmp_path, settings):
    chunk = KnowledgeChunk(
        document_id="one",
        title="One",
        version="1.0",
        document_status="active",
        section="Purpose",
        ordinal=0,
        chunk_id="a" * 64,
        content_hash="b" * 64,
        language="en",
        synthetic=True,
        text="operational",
    )
    first = _document("one", "1.0", (chunk,))
    second = _document("two", "1.0", (chunk,))
    with pytest.raises(InstitutionalKnowledgeError) as duplicate:
        from app.institutional_knowledge import validate_corpus

        validate_corpus((first, second))
    assert duplicate.value.reason == "duplicate_identity"
    corpus = _write_corpus(
        tmp_path / "corpus",
        {
            "post-consultation-results-follow-up.md": _markdown(
                document_id="shared-procedure",
                title="Shared Procedure",
                protocols=[POST_CONSULTATION_RESULT_REVIEW_V1],
                version="1.0",
            ),
            "shared-procedure-again.md": _markdown(
                document_id="shared-procedure",
                title="Shared Procedure",
                protocols=[POST_CONSULTATION_RESULT_REVIEW_V1],
                version="1.1",
            ),
        },
    )
    embedder = CountingEmbedder()
    index, _configured_settings = _open(settings, tmp_path, corpus, embedder)
    result = index.retrieve(_request())
    assert result.status == "UNAVAILABLE"
    assert result.reason == "index_not_ready"
    assert embedder.calls == []
    assert index._store.read_state().ready is False


def test_version_pin_uses_explicit_status_not_lexicographic_order(tmp_path, settings):
    corpus = _write_corpus(
        tmp_path / "versions",
        {
            "shared-procedure-old.md": _markdown(
                document_id="shared-procedure",
                title="Shared Procedure",
                protocols=[POST_CONSULTATION_RESULT_REVIEW_V1],
                version="1.10",
                status="superseded",
                sections=_vector_sections((1.0, 0.0), "older"),
            ),
            "shared-procedure-current.md": _markdown(
                document_id="shared-procedure",
                title="Shared Procedure",
                protocols=[POST_CONSULTATION_RESULT_REVIEW_V1],
                version="1.0",
                status="active",
                sections=_vector_sections((0.8, 0.6), "current"),
            ),
        },
    )
    index, _configured_settings = _open(settings, tmp_path, corpus, CountingEmbedder())
    current = index.retrieve(_request(query="query-post"))
    assert current.status == "FOUND"
    assert {chunk.version for chunk in current.chunks} == {"1.0"}
    pinned = index.retrieve(_request(query="query-post", version="1.10"))
    assert pinned.status == "FOUND"
    assert {chunk.version for chunk in pinned.chunks} == {"1.10"}
    assert pinned.chunks[0].score == pytest.approx(1.0)
    assert current.chunks[0].score == pytest.approx(0.8)


def test_rebuild_is_idempotent_removes_stale_rows_and_rejects_model_or_dimension_mix(tmp_path, settings):
    corpus = _ranked_corpus(tmp_path / "ranked")
    path = tmp_path / "institutional-knowledge.sqlite3"
    store = SQLiteInstitutionalKnowledgeIndex(path)
    store.initialize()
    mode = sqlite3.connect(path).execute("PRAGMA journal_mode").fetchone()[0]
    assert str(mode).lower() == "wal"
    assert sqlite3.connect(path).execute("PRAGMA user_version").fetchone()[0] == 1
    embedder = CountingEmbedder(model_id="model-a")
    documents = load_corpus(corpus)
    rebuild_index(store, documents, embedder)
    assert len(embedder.calls) == 1
    first_ids = {row["chunk_id"] for row in store.fetch_rows()}
    rebuild_index(store, documents, embedder)
    assert len(embedder.calls) == 1
    assert {row["chunk_id"] for row in store.fetch_rows()} == first_ids
    stale = tmp_path / "ranked" / "missed-follow-up-management.md"
    stale.unlink()
    rebuild_index(store, load_corpus(corpus), embedder)
    remaining = {row["document_id"] for row in store.fetch_rows()}
    assert "missed-follow-up-management" not in remaining
    assert remaining == {"post-consultation-results-follow-up", "care-coordination-procedures"}
    embedder.model_id = "model-b"
    rebuild_index(store, load_corpus(corpus), embedder)
    assert len(embedder.calls) == 2
    models = {row["embedding_model"] for row in store.fetch_rows()}
    assert models == {"model-b"}
    class Broken:
        model_id = "model-c"

        def embed_texts(self, texts):
            raise EmbeddingUnavailable()

    with pytest.raises(EmbeddingUnavailable):
        rebuild_index(store, load_corpus(corpus), Broken())
    assert store.read_state().ready is False
    restored = CountingEmbedder(model_id="model-b")
    rebuild_index(store, load_corpus(corpus), restored)
    class Mixed:
        model_id = "model-d"

        def embed_texts(self, texts):
            return [(1.0, 0.0) if index == 0 else (1.0, 0.0, 0.0) for index, _text in enumerate(texts)]

    with pytest.raises(InstitutionalKnowledgeError):
        rebuild_index(store, load_corpus(corpus), Mixed())
    assert store.read_state().ready is False


def test_embedding_does_not_hold_the_sqlite_write_lock(tmp_path, settings):
    corpus = _ranked_corpus(tmp_path / "lock-corpus")
    path = tmp_path / "institutional-knowledge.sqlite3"
    store = SQLiteInstitutionalKnowledgeIndex(path)
    store.initialize()

    class Probe:
        model_id = "deterministic-fake-v1"
        probed = False

        def embed_texts(self, texts):
            connection = sqlite3.connect(path, timeout=0.5)
            try:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute("ROLLBACK")
                self.probed = True
            finally:
                connection.close()
            return [(1.0, 0.0) for _text in texts]

    probe = Probe()
    rebuild_index(store, load_corpus(corpus), probe)
    assert probe.probed is True


def test_threshold_orders_cosine_and_bounds_top_k(tmp_path, settings):
    sections = {name: f"{name} operational text." for name in SECTIONS}
    sections["Purpose"] = "vector:1.0,0.0\nclearly above threshold"
    sections["Scope"] = f"vector:0.9,{CARE_Y}\nsecond match"
    sections["Operational Trigger"] = "vector:0.8,0.6\nthird match"
    sections["Review Procedure"] = f"vector:0.75,{math.sqrt(1.0 - 0.75 ** 2)}\nfourth match"
    sections["Human Authority"] = "vector:0.5,{:.17f}\nbelow threshold".format(math.sqrt(1.0 - 0.25))
    sections["Outcomes"] = "vector:0.0,1.0\northogonal"
    sections["Non-goals"] = "vector:0.0,1.0\nalso orthogonal"
    corpus = _write_corpus(
        tmp_path / "threshold",
        {
            "post-consultation-results-follow-up.md": _markdown(
                document_id="post-consultation-results-follow-up",
                title="Post-Consultation Results Follow-up Protocol",
                protocols=[POST_CONSULTATION_RESULT_REVIEW_V1],
                sections=sections,
            )
        },
    )
    index, _configured_settings = _open(settings, tmp_path, corpus, CountingEmbedder(), institutional_knowledge_min_score=0.70)
    found = index.retrieve(_request(query="query-post", topK=3))
    assert found.status == "FOUND"
    assert [chunk.section for chunk in found.chunks] == ["Purpose", "Scope", "Operational Trigger"]
    assert [chunk.score for chunk in found.chunks] == pytest.approx([1.0, 0.9, 0.8])
    assert all(chunk.content_hash and chunk.chunk_id and chunk.text for chunk in found.chunks)
    assert found.chunks[0].as_dict()["contentRole"] == "institutional_document_data"
    assert "vector" not in found.chunks[0].as_dict()
    narrow = index.retrieve(_request(query="query-post", topK=1))
    assert [chunk.section for chunk in narrow.chunks] == ["Purpose"]
    low_only = _write_corpus(
        tmp_path / "below",
        {
            "post-consultation-results-follow-up.md": _markdown(
                document_id="post-consultation-results-follow-up",
                title="Post-Consultation Results Follow-up Protocol",
                protocols=[POST_CONSULTATION_RESULT_REVIEW_V1],
                sections=_vector_sections((0.5, math.sqrt(0.75)), "below"),
            )
        },
    )
    below, _configured_settings = _open(
        settings,
        tmp_path / "below-db",
        low_only,
        CountingEmbedder(),
        institutional_knowledge_min_score=0.70,
        institutional_knowledge_db_path=str(tmp_path / "below-db" / "institutional-knowledge.sqlite3"),
    )
    missed = below.retrieve(_request(query="query-post"))
    assert missed.status == "NO_RELEVANT_GUIDANCE"
    assert missed.chunks == ()
    assert missed.reason is None


def test_protocol_filter_runs_before_ranking(tmp_path, settings):
    index, _configured_settings = _open(settings, tmp_path, _ranked_corpus(tmp_path / "filter"), CountingEmbedder())
    post = index.retrieve(_request(protocol=POST_CONSULTATION_RESULT_REVIEW_V1, query="query-post", topK=3))
    assert post.status == "FOUND"
    assert post.chunks[0].score == pytest.approx(0.9)
    assert {chunk.document_id for chunk in post.chunks} == {"care-coordination-procedures"}
    assert all(chunk.score == pytest.approx(0.9) for chunk in post.chunks)
    missed = index.retrieve(_request(protocol=MISSED_FOLLOW_UP_REVIEW_V1, query="query-missed", topK=3))
    assert missed.status == "FOUND"
    assert missed.chunks[0].score == pytest.approx(0.9 * 0.8 + CARE_Y * 0.6)
    assert missed.chunks[0].score < 1.0
    assert {chunk.document_id for chunk in missed.chunks} == {"care-coordination-procedures"}


def test_query_embedding_failure_is_unavailable_not_empty_success(tmp_path, settings):
    corpus = _ranked_corpus(tmp_path / "query-fail")
    built, _configured_settings = _open(settings, tmp_path, corpus, CountingEmbedder())

    class QueryFailure:
        model_id = "deterministic-fake-v1"

        def embed_texts(self, texts):
            raise EmbeddingUnavailable()

    built._embedder = QueryFailure()
    failed = built.retrieve(_request())
    assert failed.status == "UNAVAILABLE"
    assert failed.reason == "embedding_unavailable"
    assert failed.chunks == ()
    connection = sqlite3.connect(built._store.database_path)
    try:
        connection.execute("UPDATE institutional_vectors SET vector_json = '[NaN, 0.0]'")
        connection.commit()
    finally:
        connection.close()
    built._embedder = CountingEmbedder()
    corrupt = built.retrieve(_request())
    assert corrupt.status == "UNAVAILABLE"
    assert corrupt.reason == "vector_integrity"


def test_retrieval_does_not_call_protocol_evaluation_or_text_generation(tmp_path, settings, monkeypatch):
    def explode(*_args, **_kwargs):
        raise AssertionError("authority boundary crossed")

    monkeypatch.setattr("app.post_consultation_review.evaluate_post_consultation_review", explode)
    monkeypatch.setattr("app.missed_follow_up_review.evaluate_missed_follow_up", explode)
    monkeypatch.setattr("app.gemini_provider.GeminiProvider.generate_summary", explode)
    monkeypatch.setattr("app.gemini_provider.GeminiProvider._invoke", explode)
    index, _configured_settings = _open(settings, tmp_path, _ranked_corpus(tmp_path / "boundary"), CountingEmbedder())
    result = index.retrieve(_request())
    assert result.status == "FOUND"
    review = SQLiteFollowUpReviewCaseRepository(tmp_path / "review.sqlite3")
    review.initialize()
    index.retrieve(_request())
    connection = sqlite3.connect(review.database_path)
    try:
        assert connection.execute("SELECT COUNT(*) FROM follow_up_review_cases").fetchone()[0] == 0
    finally:
        connection.close()
    assert evaluate_post_consultation_review.__name__ == "evaluate_post_consultation_review"
    assert evaluate_missed_follow_up.__name__ == "evaluate_missed_follow_up"


def test_gemini_embedding_adapter_uses_embed_content_only(monkeypatch):
    events = []

    class Models:
        def embed_content(self, *, model, contents, config=None):
            events.append(("embed", model, list(contents), config))
            return SimpleNamespace(embeddings=[SimpleNamespace(values=[0.25, 0.5]) for _item in contents])

        def generate_content(self, *args, **kwargs):
            events.append(("generate", args, kwargs))
            raise AssertionError("generate_content")

    class Client:
        def __init__(self, *, api_key, http_options):
            assert api_key == "test-key"
            assert http_options.timeout == 30_000
            self.models = Models()

    monkeypatch.setattr("google.genai.Client", Client)
    provider = GeminiEmbeddingProvider(api_key="test-key", model="gemini-embedding-001")
    vectors = provider.embed_texts([f"text-{index}" for index in range(17)])
    assert provider.model_id == "gemini-embedding-001"
    assert len(vectors) == 17
    assert [kind for kind, *_rest in events] == ["embed", "embed"]
    assert events[0][1] == "gemini-embedding-001"
    assert events[0][3] is None
    assert len(events[0][2]) == 16
    assert len(events[1][2]) == 1
    with pytest.raises(EmbeddingUnavailable):
        GeminiEmbeddingProvider(api_key="", model="gemini-embedding-001")
    monkeypatch.setattr("google.genai.Client", lambda **_kwargs: (_ for _ in ()).throw(AssertionError("client")))
    with pytest.raises(EmbeddingUnavailable):
        GeminiEmbeddingProvider(api_key="", model="gemini-embedding-001").embed_texts(["x"])


def test_http_contract_auth_validation_and_failure_statuses(tmp_path, settings, caplog):
    index, configured = _open(settings, tmp_path, _ranked_corpus(tmp_path / "http"), CountingEmbedder())
    app.dependency_overrides[get_settings] = lambda: configured
    app.state.institutional_knowledge = index
    client = TestClient(app)
    try:
        unauthorized = client.post("/internal/knowledge/retrieve", json={"protocolId": POST_CONSULTATION_RESULT_REVIEW_V1})
        assert unauthorized.status_code == 401
        assert unauthorized.content == b""
        wrong = client.post(
            "/internal/knowledge/retrieve",
            json={"protocolId": POST_CONSULTATION_RESULT_REVIEW_V1, "queryText": "query-post"},
            headers={"X-Service-Token": "wrong"},
        )
        assert wrong.status_code == 401
        blank = _configured(settings, tmp_path, model_boundary_service_token="")
        app.dependency_overrides[get_settings] = lambda: blank
        assert client.post(
            "/internal/knowledge/retrieve",
            json={"protocolId": POST_CONSULTATION_RESULT_REVIEW_V1, "queryText": "query-post"},
            headers=AUTH,
        ).status_code == 401
        app.dependency_overrides[get_settings] = lambda: configured
        for payload in (
            {"protocolId": POST_CONSULTATION_RESULT_REVIEW_V1, "queryText": "query-post", "caseId": "SYN-FOLLOWUP-001"},
            {"protocolId": POST_CONSULTATION_RESULT_REVIEW_V1, "queryText": "query-post", "patientId": "Patient/1"},
            {"protocolId": POST_CONSULTATION_RESULT_REVIEW_V1, "queryText": "query-post", "documentPath": "../secret.md"},
            {"protocolId": POST_CONSULTATION_RESULT_REVIEW_V1, "queryText": "Patient/abc"},
            {"protocolId": "OTHER", "queryText": "query-post"},
            {"protocolId": POST_CONSULTATION_RESULT_REVIEW_V1, "queryText": ""},
            {"protocolId": POST_CONSULTATION_RESULT_REVIEW_V1, "queryText": "x" * 401},
            {"protocolId": POST_CONSULTATION_RESULT_REVIEW_V1, "queryText": "query-post", "topK": 4},
            {"protocolId": POST_CONSULTATION_RESULT_REVIEW_V1, "queryText": "query-post", "reasonCodes": ["not_a_reason"]},
            {"protocolId": POST_CONSULTATION_RESULT_REVIEW_V1, "queryText": "query-post", "version": "latest"},
        ):
            rejected = client.post("/internal/knowledge/retrieve", json=payload, headers=AUTH)
            assert rejected.status_code == 422
        caplog.clear()
        with caplog.at_level("INFO"):
            found = client.post(
                "/internal/knowledge/retrieve",
                json={
                    "protocolId": POST_CONSULTATION_RESULT_REVIEW_V1,
                    "queryText": "query-post unique-query-marker",
                    "reasonCodes": ["post_consultation_result_requires_review"],
                    "topK": 3,
                },
                headers=AUTH,
            )
        assert found.status_code == 200
        body = found.json()
        assert body["schema"] == "INSTITUTIONAL_KNOWLEDGE_RETRIEVAL_V1"
        assert body["status"] == "FOUND"
        assert body["chunks"]
        assert "vector" not in body["chunks"][0]
        assert body["chunks"][0]["contentRole"] == "institutional_document_data"
        assert "evaluationStatus" not in found.text
        assert "matchedResources" not in found.text
        assert "caseId" not in found.text
        logged = "\n".join(record.getMessage() for record in caplog.records)
        assert "unique-query-marker" not in logged
        assert TOKEN not in logged
        assert "query-post unique-query-marker" not in logged
        assert "FOUND" in logged
        assert POST_CONSULTATION_RESULT_REVIEW_V1 in logged
        low = client.post(
            "/internal/knowledge/retrieve",
            json={"protocolId": POST_CONSULTATION_RESULT_REVIEW_V1, "queryText": "query-low"},
            headers=AUTH,
        )
        assert low.status_code == 200
        assert low.json()["status"] == "NO_RELEVANT_GUIDANCE"
        assert low.json()["chunks"] == []
        index._embedder = _RaisingEmbedder()
        unavailable = client.post(
            "/internal/knowledge/retrieve",
            json={"protocolId": POST_CONSULTATION_RESULT_REVIEW_V1, "queryText": "query-post"},
            headers=AUTH,
        )
        assert unavailable.status_code == 503
        assert unavailable.json()["status"] == "UNAVAILABLE"
        assert unavailable.json()["chunks"] == []
        assert "Traceback" not in unavailable.text
    finally:
        app.dependency_overrides.clear()
        if hasattr(app.state, "institutional_knowledge"):
            del app.state.institutional_knowledge


def test_failed_knowledge_startup_does_not_block_review_startup(tmp_path, settings):
    review = SQLiteFollowUpReviewCaseRepository(tmp_path / "review.sqlite3")
    review.initialize()
    previous_repository = getattr(app.state, "followup_review_repository", None)
    application = SimpleNamespace(state=SimpleNamespace())
    configured = _configured(
        settings,
        tmp_path,
        institutional_knowledge_db_path=str(tmp_path / "knowledge.sqlite3"),
        followup_agent_enabled=False,
        ai_review_db_path=str(tmp_path / "review.sqlite3"),
        human_session_db_path=str(tmp_path / "human-session.sqlite3"),
        human_review_form_signing_secret="synthetic-form-signing-secret-b",
        human_review_development_auth_enabled=True,
        human_review_development_auth_secret="development-secret-value-32chars-min",
        human_review_development_principal_id="lab-reviewer",
        human_review_development_principal_display_name="Lab reviewer",
    )
    attach_institutional_knowledge(application, configured, corpus_root=tmp_path / "missing-corpus")
    result = application.state.institutional_knowledge.retrieve(_request())
    assert result.status == "UNAVAILABLE"
    review.initialize()
    connection = sqlite3.connect(review.database_path)
    try:
        assert connection.execute("SELECT COUNT(*) FROM follow_up_review_cases").fetchone()[0] == 0
    finally:
        connection.close()
    session_store = SQLiteHumanSessionRepository(tmp_path / "human-session.sqlite3")
    session_store.initialize()
    app.dependency_overrides[get_settings] = lambda: configured
    app.state.institutional_knowledge = application.state.institutional_knowledge
    app.state.followup_review_repository = review
    app.state.human_session_repository = session_store
    try:
        response = TestClient(app).post(
            "/internal/agent/follow-up",
            json={"caseId": "SYN-FOLLOWUP-001"},
            headers=AUTH,
        )
        assert response.status_code == 503
        assert response.json()["detail"] == "Follow-up agent is disabled"
        client = TestClient(app, base_url="http://127.0.0.1")
        signed_in = client.post(
            "/review-login",
            content=urlencode({"developmentSecret": "development-secret-value-32chars-min"}),
            headers={"origin": "http://127.0.0.1", "content-type": "application/x-www-form-urlencoded"},
            follow_redirects=False,
        )
        assert signed_in.status_code == 303
        page = client.get("/review-cases")
        assert page.status_code == 200
        assert "knowledge/retrieve" not in page.text
        assert "institutional" not in page.text.casefold()
    finally:
        app.dependency_overrides.clear()
        if hasattr(app.state, "institutional_knowledge"):
            del app.state.institutional_knowledge
        if hasattr(app.state, "human_session_repository"):
            del app.state.human_session_repository
        if previous_repository is None:
            if hasattr(app.state, "followup_review_repository"):
                del app.state.followup_review_repository
        else:
            app.state.followup_review_repository = previous_repository


def test_settings_keep_the_knowledge_index_separate(monkeypatch):
    monkeypatch.delenv("INSTITUTIONAL_KNOWLEDGE_DB_PATH", raising=False)
    monkeypatch.delenv("INSTITUTIONAL_KNOWLEDGE_EMBEDDING_MODEL", raising=False)
    monkeypatch.delenv("INSTITUTIONAL_KNOWLEDGE_MIN_SCORE", raising=False)
    loaded = Settings.from_env()
    assert loaded.institutional_knowledge_db_path == "./data/institutional-knowledge.sqlite3"
    assert loaded.institutional_knowledge_embedding_model == "gemini-embedding-001"
    assert loaded.institutional_knowledge_min_score == 0.68
    assert loaded.institutional_knowledge_db_path != loaded.ai_review_db_path
    monkeypatch.setenv("INSTITUTIONAL_KNOWLEDGE_DB_PATH", " ")
    with pytest.raises(ValueError):
        Settings.from_env()
    monkeypatch.setenv("INSTITUTIONAL_KNOWLEDGE_DB_PATH", "./data/institutional-knowledge.sqlite3")
    monkeypatch.setenv("INSTITUTIONAL_KNOWLEDGE_MIN_SCORE", "2")
    with pytest.raises(ValueError):
        Settings.from_env()
    monkeypatch.setenv("INSTITUTIONAL_KNOWLEDGE_MIN_SCORE", "0.70")
    monkeypatch.setenv("INSTITUTIONAL_KNOWLEDGE_EMBEDDING_MODEL", "")
    with pytest.raises(ValueError):
        Settings.from_env()
    with pytest.raises(Exception):
        SQLiteInstitutionalKnowledgeIndex(":memory:")


def test_future_schema_and_unexpected_corpus_entries_fail_closed(tmp_path, settings):
    future = tmp_path / "future.sqlite3"
    with sqlite3.connect(future) as connection:
        connection.execute("PRAGMA user_version=99")
    with pytest.raises(Exception):
        SQLiteInstitutionalKnowledgeIndex(future).initialize()
    corpus = _ranked_corpus(tmp_path / "extra")
    (corpus / "notes.txt").write_text("not a document", encoding="utf-8")
    index, _configured_settings = _open(settings, tmp_path, corpus, CountingEmbedder())
    assert index.retrieve(_request()).status == "UNAVAILABLE"
    oversized = tmp_path / "big"
    oversized.mkdir()
    (oversized / "post-consultation-results-follow-up.md").write_bytes(b"x" * 32_769)
    big, _configured_settings = _open(
        settings,
        tmp_path / "big-db",
        oversized,
        CountingEmbedder(),
        institutional_knowledge_db_path=str(tmp_path / "big-db" / "institutional-knowledge.sqlite3"),
    )
    assert big.retrieve(_request()).status == "UNAVAILABLE"


def test_returned_markdown_stays_data(tmp_path, settings):
    sections = _vector_sections((0.0, 1.0), "marker")
    sections["Purpose"] = "vector:1.0,0.0\n**not html** <script>alert(1)</script>"
    corpus = _write_corpus(
        tmp_path / "html",
        {
            "post-consultation-results-follow-up.md": _markdown(
                document_id="post-consultation-results-follow-up",
                title="Post-Consultation Results Follow-up Protocol",
                protocols=[POST_CONSULTATION_RESULT_REVIEW_V1],
                sections=sections,
            )
        },
    )
    index, configured = _open(settings, tmp_path, corpus, CountingEmbedder())
    app.dependency_overrides[get_settings] = lambda: configured
    app.state.institutional_knowledge = index
    try:
        response = TestClient(app).post(
            "/internal/knowledge/retrieve",
            json={"protocolId": POST_CONSULTATION_RESULT_REVIEW_V1, "queryText": "query-post", "topK": 1},
            headers=AUTH,
        )
    finally:
        app.dependency_overrides.clear()
        if hasattr(app.state, "institutional_knowledge"):
            del app.state.institutional_knowledge
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["chunks"][0]["text"].startswith("vector:1.0,0.0")
    assert "<script>alert(1)</script>" in response.json()["chunks"][0]["text"]
    assert "<html" not in response.text.casefold()
    source = Path(__file__).resolve().parents[1].joinpath("app", "human_review_client.py").read_text(encoding="utf-8")
    assert "/internal/knowledge/retrieve" not in source
    for name in (
        "institutional_knowledge.py",
        "institutional_knowledge_http.py",
        "institutional_knowledge_sqlite.py",
        "institutional_embeddings.py",
    ):
        module = Path(__file__).resolve().parents[1].joinpath("app", name).read_text(encoding="utf-8").lower()
        assert "langgraph" not in module
        assert "generate_content" not in module


def _document(document_id: str, version: str, chunks: tuple[KnowledgeChunk, ...]) -> InstitutionalDocument:
    return InstitutionalDocument(
        document_id=document_id,
        title="Procedure",
        version=version,
        status="active",
        effective_date="2026-10-06",
        source_type="synthetic_institutional_procedure",
        synthetic=True,
        protocol_ids=(POST_CONSULTATION_RESULT_REVIEW_V1,),
        language="en",
        content_hash="c" * 64,
        chunks=chunks,
    )


def _ranked_corpus(directory: Path) -> Path:
    return _write_corpus(
        directory,
        {
            "post-consultation-results-follow-up.md": _markdown(
                document_id="post-consultation-results-follow-up",
                title="Post-Consultation Results Follow-up Protocol",
                protocols=[POST_CONSULTATION_RESULT_REVIEW_V1],
                sections=_vector_sections(POST_VECTOR, "post"),
            ),
            "missed-follow-up-management.md": _markdown(
                document_id="missed-follow-up-management",
                title="Missed Follow-up Management Protocol",
                protocols=[MISSED_FOLLOW_UP_REVIEW_V1],
                sections=_vector_sections(MISSED_VECTOR, "missed"),
            ),
            "care-coordination-procedures.md": _markdown(
                document_id="care-coordination-procedures",
                title="Care Coordination Procedures",
                protocols=[POST_CONSULTATION_RESULT_REVIEW_V1, MISSED_FOLLOW_UP_REVIEW_V1],
                sections=_vector_sections(CARE_VECTOR, "care"),
            ),
        },
    )


class _RaisingEmbedder:
    model_id = "deterministic-fake-v1"

    def embed_texts(self, texts):
        raise EmbeddingUnavailable()
