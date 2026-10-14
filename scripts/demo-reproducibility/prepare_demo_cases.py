"""Prepare two disposable synthetic review cases on a local review database.

This operator utility loads the five named fixtures, reads them back through
the existing FHIR acquisition, and calls ensure_for_protocol. It does not call
Gemini, LangGraph, or the follow-up agent endpoints.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import sqlite3
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol
from urllib.parse import urlsplit

from app.followup_review import (
    FollowUpReviewCaseService,
    ReviewCaseStatus,
    build_review_identity,
)
from app.followup_review_sqlite import (
    BUSY_TIMEOUT_MS,
    SCHEMA_VERSION,
    ReviewStoreInitializationError,
    SQLiteFollowUpReviewCaseRepository,
)
from app.langgraph_fhir_client import FHIRTransport, ReadClientError
from app.langgraph_fhir_followup import FollowUpFHIRAdapter, PostConsultationContextReader
from app.missed_follow_up_review import MISSED_FOLLOW_UP_REVIEW_V1, REASON_MISSED
from app.missed_follow_up_service import evaluate_missed_follow_up_case
from app.post_consultation_review import (
    POST_CONSULTATION_RESULT_REVIEW_V1,
    ProtocolEvaluationStatus,
    ProtocolReviewResult,
    evaluate_post_consultation_review,
)


CASE_SYSTEM = "https://lab.local/followup-case"
SERVICE_HOST = "127.0.0.1"
SERVICE_PORT = 8090
HISTORICAL_CASE_IDS = ("SYN-FOLLOWUP-006", "SYN-FOLLOWUP-008", "SYN-FOLLOWUP-012")
HISTORICAL_MARKERS = HISTORICAL_CASE_IDS + (
    "SYN-PATIENT-006",
    "SYN-PATIENT-008",
    "SYN-PATIENT-012",
    "syn-encounter-012",
    "syn-observation-012",
    "obs-synthetic-006",
)
SESSION_TABLES = frozenset({"human_sessions"})
KNOWLEDGE_TABLES = frozenset(
    {
        "knowledge_index_state",
        "institutional_documents",
        "institutional_chunks",
        "institutional_vectors",
    }
)
REVIEW_TABLES = (
    "follow_up_review_cases",
    "follow_up_review_case_events",
    "follow_up_coordination_requests",
    "follow_up_human_attributions",
    "follow_up_coordination_request_events",
)
POST_MATCHED = ("Encounter/syn-demo-enc-101", "Observation/syn-demo-obs-101")
MISSED_MATCHED = ("Appointment/syn-demo-noshow-102",)
_DEMO_PATIENT_READS = frozenset({"syn-demo-patient-101", "syn-demo-patient-102"})
_FIXTURE_ROOT = Path(__file__).resolve().parent
_HISTORICAL_FIXTURE_DIR = _FIXTURE_ROOT.parent / "fhir"


class DemoPreparationAborted(Exception):
    """Preparation stopped before creating or reopening a review case."""

    def __init__(self, reason: str, detail: str) -> None:
        self.reason = reason
        super().__init__(detail)


@dataclass(frozen=True)
class PreparedDemoCase:
    case_id: str
    protocol_id: str
    status: str
    review_case_id: str


@dataclass(frozen=True)
class DemoPreparationReport:
    cases: tuple[PreparedDemoCase, ...]


@dataclass(frozen=True)
class _DemoCase:
    case_id: str
    protocol_id: str
    patient_id: str
    allowed_references: frozenset[str]


@dataclass(frozen=True)
class _DemoResource:
    case: _DemoCase
    resource_type: str
    resource_id: str
    filename: str


@dataclass(frozen=True)
class _ExistingReviewRow:
    review_case_id: str
    case_id: str
    protocol_id: str
    status: str
    review_identity: str


class DemoFhirGateway(Protocol):
    def read_exact(self, resource_type: str, resource_id: str) -> dict | None: ...

    def put_resource(self, resource: Mapping[str, object]) -> None: ...

    def transport(self) -> FHIRTransport: ...


_POST = _DemoCase(
    case_id="SYN-DEMO-101",
    protocol_id=POST_CONSULTATION_RESULT_REVIEW_V1,
    patient_id="syn-demo-patient-101",
    allowed_references=frozenset(
        {
            "Patient/syn-demo-patient-101",
            "Encounter/syn-demo-enc-101",
            "Observation/syn-demo-obs-101",
        }
    ),
)
_MISSED = _DemoCase(
    case_id="SYN-DEMO-102",
    protocol_id=MISSED_FOLLOW_UP_REVIEW_V1,
    patient_id="syn-demo-patient-102",
    allowed_references=frozenset(
        {
            "Patient/syn-demo-patient-102",
            "Appointment/syn-demo-noshow-102",
        }
    ),
)
_RESOURCES = (
    _DemoResource(_POST, "Patient", "syn-demo-patient-101", "syn-demo-patient-101.json"),
    _DemoResource(_POST, "Encounter", "syn-demo-enc-101", "syn-demo-enc-101.json"),
    _DemoResource(_POST, "Observation", "syn-demo-obs-101", "syn-demo-obs-101.json"),
    _DemoResource(_MISSED, "Patient", "syn-demo-patient-102", "syn-demo-patient-102.json"),
    _DemoResource(_MISSED, "Appointment", "syn-demo-noshow-102", "syn-demo-noshow-102.json"),
)
_CASES = (_POST, _MISSED)


def tcp_accepts(host: str, port: int, timeout: float = 0.5) -> bool:
    """Return whether a TCP handshake completes. Refusal or timeout means it does not."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (ConnectionRefusedError, TimeoutError):
        return False
    except OSError as exc:
        raise DemoPreparationAborted(
            "service_check_failed",
            "Healthcare AI availability check failed",
        ) from exc


def prepare_demo_review(
    *,
    review_db_path: str,
    configured_review_db_path: str,
    session_db_path: str,
    knowledge_db_path: str,
    fhir_base_url: str,
    gateway: DemoFhirGateway,
    fixture_dir: Path | None = None,
    service_accepts_connections: Callable[[], bool] | None = None,
    clock: Callable[[], datetime] | None = None,
    busy_timeout_ms: int = BUSY_TIMEOUT_MS,
) -> DemoPreparationReport:
    """Create or reuse one open review case for each disposable demo id."""
    review_path = _authorized_review_path(
        review_db_path,
        configured_review_db_path,
        session_db_path,
        knowledge_db_path,
    )
    _require_loopback(fhir_base_url)
    if service_accepts_connections is None:
        accepting = tcp_accepts(SERVICE_HOST, SERVICE_PORT)
    else:
        try:
            accepting = service_accepts_connections()
        except OSError as exc:
            raise DemoPreparationAborted(
                "service_check_failed",
                "Healthcare AI availability check failed",
            ) from exc
    if accepting:
        raise DemoPreparationAborted(
            "service_accepting_connections",
            "Healthcare AI accepts connections on 127.0.0.1:8090",
        )
    directory = _require_fixture_dir(fixture_dir or _FIXTURE_ROOT)
    if busy_timeout_ms < 0:
        raise DemoPreparationAborted(
            "exclusive_lock_unavailable",
            "exclusive review database lock was not acquired",
        )
    existing = _inspect_review_store(review_path, busy_timeout_ms)
    _guard_existing(existing)
    fixtures = _load_fixtures(directory)
    _replace_owned_resources(gateway, fixtures)
    instant = (clock or _utc_now)()
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise DemoPreparationAborted(
            "evaluation_not_matched",
            "evaluation instant must be timezone-aware",
        )
    protocols = _evaluate(gateway, instant)
    existing = _inspect_review_store(review_path, busy_timeout_ms)
    _guard_existing(existing)
    for case_spec, protocol in protocols:
        _guard_identity(existing, case_spec, protocol)
    repository = SQLiteFollowUpReviewCaseRepository(review_path)
    service = FollowUpReviewCaseService(repository)
    prepared: list[PreparedDemoCase] = []
    for case_spec, protocol in protocols:
        case = service.ensure_for_protocol(case_spec.case_id, protocol)
        if case is None or case.status is not ReviewCaseStatus.OPEN:
            raise DemoPreparationAborted(
                "review_case_closed",
                "disposable review case is closed; explicit reset is required",
            )
        if case.case_id != case_spec.case_id or case.protocol_id != case_spec.protocol_id:
            raise DemoPreparationAborted(
                "review_protocol_mismatch",
                "disposable case id has a different protocol",
            )
        prepared.append(
            PreparedDemoCase(
                case_id=case.case_id,
                protocol_id=case.protocol_id,
                status=case.status.value,
                review_case_id=case.id,
            )
        )
    return DemoPreparationReport(cases=tuple(prepared))


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _require_loopback(fhir_base_url: str) -> str:
    parsed = urlsplit(fhir_base_url.strip())
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.hostname not in {"127.0.0.1", "localhost"}
        or parsed.username
        or parsed.password
    ):
        raise DemoPreparationAborted(
            "fhir_base_url_not_loopback",
            "FHIR base URL must be an explicit loopback URL",
        )
    return fhir_base_url.rstrip("/")


def _authorized_review_path(
    review_db_path: str,
    configured_review_db_path: str,
    session_db_path: str,
    knowledge_db_path: str,
) -> Path:
    if not session_db_path.strip() or not knowledge_db_path.strip():
        raise DemoPreparationAborted(
            "review_db_path_invalid",
            "session and knowledge database paths must be explicit",
        )
    review_path = _existing_absolute_file(review_db_path)
    if review_path == _resolved_path(session_db_path):
        raise DemoPreparationAborted(
            "session_database",
            "review database path is the session database",
        )
    if review_path == _resolved_path(knowledge_db_path):
        raise DemoPreparationAborted(
            "knowledge_database",
            "review database path is the institutional knowledge database",
        )
    if not configured_review_db_path.strip():
        raise DemoPreparationAborted(
            "review_db_not_configured",
            "AI_REVIEW_DB_PATH must be explicit",
        )
    if review_path != _resolved_path(configured_review_db_path):
        raise DemoPreparationAborted(
            "review_db_not_configured",
            "review database path is not the configured local review store",
        )
    return review_path


def _existing_absolute_file(path: str) -> Path:
    candidate = Path(path)
    if not path.strip() or not candidate.is_absolute():
        raise DemoPreparationAborted(
            "review_db_path_invalid",
            "review database path must be absolute",
        )
    if not candidate.is_file():
        raise DemoPreparationAborted(
            "review_db_missing",
            "review database file does not exist",
        )
    return candidate.resolve()


def _resolved_path(path: str) -> Path:
    return Path(path).expanduser().resolve()


def _require_fixture_dir(directory: Path) -> Path:
    resolved = directory.resolve()
    historical = _HISTORICAL_FIXTURE_DIR.resolve()
    if resolved == historical or historical in resolved.parents:
        raise DemoPreparationAborted(
            "fixture_directory_rejected",
            "demo fixtures must stay outside scripts/fhir",
        )
    if not resolved.is_dir():
        raise DemoPreparationAborted("fixture_invalid", "demo fixture directory is missing")
    return resolved


def _inspect_review_store(review_path: Path, busy_timeout_ms: int) -> tuple[_ExistingReviewRow, ...]:
    connection = sqlite3.connect(
        review_path,
        timeout=busy_timeout_ms / 1000,
        isolation_level=None,
    )
    try:
        connection.row_factory = sqlite3.Row
        connection.execute(f"PRAGMA busy_timeout={int(busy_timeout_ms)}")
        connection.execute("PRAGMA foreign_keys=ON")
        if int(connection.execute("PRAGMA foreign_keys").fetchone()[0]) != 1:
            raise DemoPreparationAborted(
                "schema_incompatible",
                "review database schema is incompatible",
            )
        connection.execute("BEGIN IMMEDIATE")
        try:
            repository = SQLiteFollowUpReviewCaseRepository(review_path)
            repository._validate_schema(connection)
            if int(connection.execute("PRAGMA user_version").fetchone()[0]) != SCHEMA_VERSION:
                raise DemoPreparationAborted(
                    "schema_incompatible",
                    "review database schema is incompatible",
                )
            names = {
                str(row[0])
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            if SESSION_TABLES & names:
                raise DemoPreparationAborted(
                    "session_database",
                    "review database path is the session database",
                )
            if KNOWLEDGE_TABLES & names:
                raise DemoPreparationAborted(
                    "knowledge_database",
                    "review database path is the institutional knowledge database",
                )
            if not set(REVIEW_TABLES).issubset(names):
                raise DemoPreparationAborted(
                    "schema_incompatible",
                    "review database schema is incompatible",
                )
            rows = connection.execute(
                """
                SELECT id, case_id, protocol_id, status, review_identity
                FROM follow_up_review_cases
                WHERE case_id IN (?, ?)
                """,
                (_POST.case_id, _MISSED.case_id),
            ).fetchall()
            return tuple(
                _ExistingReviewRow(
                    review_case_id=str(row["id"]),
                    case_id=str(row["case_id"]),
                    protocol_id=str(row["protocol_id"]),
                    status=str(row["status"]),
                    review_identity=str(row["review_identity"]),
                )
                for row in rows
            )
        finally:
            connection.rollback()
    except DemoPreparationAborted:
        raise
    except ReviewStoreInitializationError as exc:
        raise DemoPreparationAborted(
            "schema_incompatible",
            "review database schema is incompatible",
        ) from exc
    except sqlite3.OperationalError as exc:
        if "locked" in str(exc).lower():
            raise DemoPreparationAborted(
                "exclusive_lock_unavailable",
                "exclusive review database lock was not acquired",
            ) from exc
        raise DemoPreparationAborted(
            "schema_incompatible",
            "review database schema is incompatible",
        ) from exc
    finally:
        connection.close()


def _guard_existing(rows: tuple[_ExistingReviewRow, ...]) -> None:
    grouped: dict[str, list[_ExistingReviewRow]] = {case.case_id: [] for case in _CASES}
    for row in rows:
        if row.case_id in HISTORICAL_CASE_IDS:
            raise DemoPreparationAborted(
                "historical_case_protected",
                "historical review rows are not disposable",
            )
        if row.case_id not in grouped:
            raise DemoPreparationAborted(
                "review_protocol_mismatch",
                "disposable case id has a different protocol",
            )
        grouped[row.case_id].append(row)
    for case_spec in _CASES:
        found = grouped[case_spec.case_id]
        if len(found) > 1:
            raise DemoPreparationAborted(
                "review_protocol_mismatch",
                "disposable case id has more than one review row",
            )
        if not found:
            continue
        row = found[0]
        if row.protocol_id != case_spec.protocol_id:
            raise DemoPreparationAborted(
                "review_protocol_mismatch",
                "disposable case id has a different protocol",
            )
        if row.status == ReviewCaseStatus.CLOSED.value:
            raise DemoPreparationAborted(
                "review_case_closed",
                "disposable review case is closed; explicit reset is required",
            )
        if row.status != ReviewCaseStatus.OPEN.value:
            raise DemoPreparationAborted(
                "schema_incompatible",
                "review database schema is incompatible",
            )


def _guard_identity(
    rows: tuple[_ExistingReviewRow, ...],
    case_spec: _DemoCase,
    protocol: ProtocolReviewResult,
) -> None:
    identity = build_review_identity(
        case_spec.case_id,
        protocol.id,
        protocol.matched_resources,
    )
    for row in rows:
        if row.case_id != case_spec.case_id:
            continue
        if row.review_identity != identity:
            raise DemoPreparationAborted(
                "unexpected_review_identity",
                "open disposable case does not match the current protocol result",
            )


def _load_fixtures(directory: Path) -> tuple[tuple[_DemoResource, dict], ...]:
    loaded: list[tuple[_DemoResource, dict]] = []
    for spec in _RESOURCES:
        path = directory / spec.filename
        if not path.is_file():
            raise DemoPreparationAborted("fixture_invalid", "named demo fixture is missing")
        try:
            body = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise DemoPreparationAborted(
                "fixture_invalid",
                "named demo fixture is not valid JSON",
            ) from exc
        if not isinstance(body, dict):
            raise DemoPreparationAborted("fixture_invalid", "named demo fixture is not a JSON object")
        _assert_owned(body, spec, "fixture_invalid")
        loaded.append((spec, body))
    return tuple(loaded)


def _replace_owned_resources(
    gateway: DemoFhirGateway,
    fixtures: tuple[tuple[_DemoResource, dict], ...],
) -> None:
    checked: list[tuple[_DemoResource, dict]] = []
    for spec, body in fixtures:
        try:
            current = gateway.read_exact(spec.resource_type, spec.resource_id)
        except ReadClientError as exc:
            raise DemoPreparationAborted("fhir_connection_error", "FHIR read failed") from exc
        if current is not None:
            _assert_owned(current, spec, "fhir_ownership_rejected")
        checked.append((spec, body))
    for spec, body in checked:
        try:
            gateway.put_resource(body)
        except ReadClientError as exc:
            raise DemoPreparationAborted("fhir_connection_error", "FHIR write failed") from exc


def _assert_owned(resource: Mapping[str, object], spec: _DemoResource, reason: str) -> None:
    if resource.get("resourceType") != spec.resource_type or resource.get("id") != spec.resource_id:
        raise DemoPreparationAborted(reason, "FHIR resource is not one of the disposable ids")
    _reject_historical_text(resource, reason)
    for reference in _references(resource):
        if reference not in spec.case.allowed_references:
            raise DemoPreparationAborted(
                reason,
                "FHIR resource is not owned by the disposable demo patient",
            )
    if spec.resource_type == "Patient":
        if _case_identifier_values(resource) != (spec.case.case_id,):
            raise DemoPreparationAborted(
                reason,
                "FHIR patient identifier is not the disposable case id",
            )
        return
    if spec.resource_type == "Encounter":
        expected = f"Patient/{spec.case.patient_id}"
        if _field_reference(resource, "subject") != expected:
            raise DemoPreparationAborted(
                reason,
                "FHIR encounter is not owned by the disposable demo patient",
            )
        return
    if spec.resource_type == "Observation":
        if _field_reference(resource, "subject") != f"Patient/{spec.case.patient_id}":
            raise DemoPreparationAborted(
                reason,
                "FHIR observation is not owned by the disposable demo patient",
            )
        if _field_reference(resource, "encounter") != "Encounter/syn-demo-enc-101":
            raise DemoPreparationAborted(
                reason,
                "FHIR observation is not owned by the disposable encounter",
            )
        return
    participant_refs = _participant_references(resource)
    expected = f"Patient/{spec.case.patient_id}"
    if not participant_refs or any(reference != expected for reference in participant_refs):
        raise DemoPreparationAborted(
            reason,
            "FHIR appointment is not owned by the disposable demo patient",
        )


def _reject_historical_text(resource: Mapping[str, object], reason: str) -> None:
    for text in _strings(resource):
        for marker in HISTORICAL_MARKERS:
            if marker in text:
                raise DemoPreparationAborted(
                    reason,
                    "FHIR resource references a historical case",
                )


def _strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        found: list[str] = []
        for item in value.values():
            found.extend(_strings(item))
        return found
    if isinstance(value, list):
        found = []
        for item in value:
            found.extend(_strings(item))
        return found
    return []


def _references(value: object) -> list[str]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key == "reference" and isinstance(item, str):
                found.append(item)
            else:
                found.extend(_references(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(_references(item))
    return found


def _field_reference(resource: Mapping[str, object], field: str) -> str | None:
    value = resource.get(field)
    if not isinstance(value, Mapping):
        return None
    reference = value.get("reference")
    return reference if isinstance(reference, str) else None


def _participant_references(resource: Mapping[str, object]) -> tuple[str, ...]:
    participants = resource.get("participant")
    if not isinstance(participants, list):
        return ()
    references: list[str] = []
    for item in participants:
        if not isinstance(item, Mapping):
            continue
        actor = item.get("actor")
        if isinstance(actor, Mapping) and isinstance(actor.get("reference"), str):
            references.append(str(actor["reference"]))
    return tuple(references)


def _case_identifier_values(resource: Mapping[str, object]) -> tuple[str, ...]:
    identifiers = resource.get("identifier")
    if not isinstance(identifiers, list):
        return ()
    values: list[str] = []
    for item in identifiers:
        if (
            isinstance(item, Mapping)
            and item.get("system") == CASE_SYSTEM
            and isinstance(item.get("value"), str)
        ):
            values.append(str(item["value"]))
    return tuple(values)


def _evaluate(
    gateway: DemoFhirGateway,
    instant: datetime,
) -> tuple[tuple[_DemoCase, ProtocolReviewResult], ...]:
    transport = gateway.transport()
    post_adapter = FollowUpFHIRAdapter(transport, now=lambda: instant)
    try:
        with post_adapter.bind_read(_POST.case_id):
            snapshot = PostConsultationContextReader(post_adapter).read(_POST.case_id)
    except ReadClientError as exc:
        raise DemoPreparationAborted("fhir_connection_error", "FHIR read failed") from exc
    post = evaluate_post_consultation_review(snapshot)
    if (
        post.evaluation_status is not ProtocolEvaluationStatus.MATCHED
        or post.matched_resources != POST_MATCHED
    ):
        raise DemoPreparationAborted(
            "evaluation_not_matched",
            "post-consultation evaluation was not matched for SYN-DEMO-101",
        )
    missed_adapter = FollowUpFHIRAdapter(transport, now=lambda: instant)
    try:
        missed = evaluate_missed_follow_up_case(missed_adapter, _MISSED.case_id, instant)
    except ReadClientError as exc:
        raise DemoPreparationAborted("fhir_connection_error", "FHIR read failed") from exc
    if missed.status is ProtocolEvaluationStatus.UNAVAILABLE:
        raise DemoPreparationAborted("fhir_connection_error", "FHIR read failed")
    if missed.status is not ProtocolEvaluationStatus.MATCHED or missed.triggers != MISSED_MATCHED:
        raise DemoPreparationAborted(
            "evaluation_not_matched",
            "missed follow-up evaluation was not matched for SYN-DEMO-102",
        )
    missed_protocol = ProtocolReviewResult(
        id=MISSED_FOLLOW_UP_REVIEW_V1,
        evaluation_status=ProtocolEvaluationStatus.MATCHED,
        reason_codes=(REASON_MISSED,),
        matched_resources=missed.triggers,
        human_review_status="required",
        human_review_reason="deterministic_missed_follow_up_protocol_match",
        action_status="proposed",
        action_type="review_follow_up_case",
    )
    return ((_POST, post), (_MISSED, missed_protocol))


def _http_get_demo_patient(url: str, accept: str):
    import httpx

    try:
        return httpx.get(
            url,
            headers={"Accept": accept},
            timeout=5.0,
            follow_redirects=False,
        )
    except httpx.HTTPError as exc:
        raise ReadClientError("FHIR read failed") from exc


def _patient_transport_failure(exc: BaseException) -> bool:
    if isinstance(exc, (TimeoutError, ConnectionError)):
        return True
    import httpx

    return isinstance(exc, httpx.HTTPError)


def _demo_patient_from_response(patient_id: str, response: object) -> dict | None:
    status = getattr(response, "status_code", None)
    if status == 404:
        return None
    if status != 200:
        raise DemoPreparationAborted(
            "fhir_unexpected_response",
            "FHIR patient read returned an unexpected status",
        )
    try:
        payload = response.json()
    except (AttributeError, TypeError, ValueError) as exc:
        raise DemoPreparationAborted(
            "fhir_ownership_rejected",
            "FHIR patient read did not prove ownership",
        ) from exc
    if not isinstance(payload, dict) or payload.get("resourceType") != "Patient" or payload.get("id") != patient_id:
        raise DemoPreparationAborted(
            "fhir_ownership_rejected",
            "FHIR patient read did not prove ownership",
        )
    return payload


class LoopbackFhirGateway:
    """PUT and read the named resources on one loopback FHIR base URL.

    Patient existence uses a local GET limited to the two disposable ids.
    Encounter, Observation, and Appointment keep the service read_exact allowlist.
    """

    def __init__(
        self,
        base_url: str,
        *,
        patient_get: Callable[..., object] | None = None,
        reader: object | None = None,
    ) -> None:
        from app.langgraph_fhir_client import ClientFHIRTransport
        from app.langgraph_fhir_hapi import ACCEPT, ExactResourceNotFound, HapiReadClient

        self._base_url = _require_loopback(base_url)
        self._exact_not_found = ExactResourceNotFound
        self._accept = ACCEPT
        self._patient_get = patient_get
        self._reader = HapiReadClient(self._base_url) if reader is None else reader
        self._transport = ClientFHIRTransport(self._reader)

    def read_exact(self, resource_type: str, resource_id: str) -> dict | None:
        if resource_type == "Patient":
            return self._read_demo_patient(resource_id)
        try:
            return self._reader.read_exact(resource_type, resource_id)
        except self._exact_not_found:
            return None

    def _read_demo_patient(self, patient_id: str) -> dict | None:
        if patient_id not in _DEMO_PATIENT_READS:
            raise DemoPreparationAborted(
                "fhir_ownership_rejected",
                "FHIR patient read is limited to the disposable demo patients",
            )
        getter = self._patient_get or _http_get_demo_patient
        try:
            response = getter(f"{self._base_url}/Patient/{patient_id}", self._accept)
        except DemoPreparationAborted:
            raise
        except ReadClientError:
            raise
        except Exception as exc:
            if _patient_transport_failure(exc):
                raise ReadClientError("FHIR read failed") from exc
            raise
        return _demo_patient_from_response(patient_id, response)

    def put_resource(self, resource: Mapping[str, object]) -> None:
        import httpx

        resource_type = resource.get("resourceType")
        resource_id = resource.get("id")
        if not isinstance(resource_type, str) or not isinstance(resource_id, str):
            raise ReadClientError("FHIR write failed")
        url = f"{self._base_url}/{resource_type}/{resource_id}"
        try:
            response = httpx.put(
                url,
                json=dict(resource),
                headers={"Accept": self._accept, "Content-Type": "application/fhir+json"},
                timeout=5.0,
                follow_redirects=False,
            )
        except httpx.HTTPError as exc:
            raise ReadClientError("FHIR write failed") from exc
        if response.status_code not in {200, 201}:
            raise ReadClientError("FHIR write failed")

    def transport(self) -> FHIRTransport:
        return self._transport


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare disposable synthetic review cases.")
    parser.add_argument("--review-db", required=True)
    parser.add_argument("--fhir-base-url", required=True)
    args = parser.parse_args(argv)
    try:
        report = prepare_demo_review(
            review_db_path=args.review_db,
            configured_review_db_path=os.environ.get("AI_REVIEW_DB_PATH", ""),
            session_db_path=os.environ.get("HUMAN_SESSION_DB_PATH", ""),
            knowledge_db_path=os.environ.get("INSTITUTIONAL_KNOWLEDGE_DB_PATH", ""),
            fhir_base_url=args.fhir_base_url,
            gateway=LoopbackFhirGateway(args.fhir_base_url),
        )
    except DemoPreparationAborted as exc:
        print(f"{exc.reason}: {exc}", file=sys.stderr)
        return 2
    for case in report.cases:
        print(f"{case.case_id} {case.protocol_id} {case.status} {case.review_case_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
