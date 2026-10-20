"""Preparation of disposable demo review cases. Scripted FHIR and a temporary database."""

from __future__ import annotations

import copy
import importlib.util
import json
import shutil
import socket
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

import pytest
from pydantic import ValidationError

from app.followup_models import CASE_IDS, FollowUpRequest
from app.followup_review import (
    FollowUpReviewTrigger,
    ReviewOutcome,
    build_review_identity,
)
from app.followup_review_sqlite import SQLiteFollowUpReviewCaseRepository
from app.human_attribution import DEVELOPMENT_AUTHENTICATOR_V1, DevelopmentPrincipalSnapshot
from app.langgraph_fhir_client import (
    BoundedSearchResult,
    BoundedSearchStatus,
    ClientFHIRTransport,
    ReadClientError,
)
from app.missed_follow_up_review import MISSED_FOLLOW_UP_REVIEW_V1, REASON_MISSED
from app.post_consultation_review import POST_CONSULTATION_RESULT_REVIEW_V1

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_DIR = REPO_ROOT / "scripts" / "demo-reproducibility"
PREPARE_PATH = FIXTURE_DIR / "prepare_demo_cases.py"
HISTORICAL_CASE_IDS = ("SYN-FOLLOWUP-006", "SYN-FOLLOWUP-008", "SYN-FOLLOWUP-012")
INSTANT = datetime(2026, 10, 8, 16, 0, tzinfo=timezone.utc)
FHIR_URL = "http://127.0.0.1:8080/fhir"


def _load_prepare():
    spec = importlib.util.spec_from_file_location("prepare_demo_cases", PREPARE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


prepare = _load_prepare()


class ScriptedFhir:
    def __init__(self) -> None:
        self.store: dict[tuple[str, str], dict] = {}
        self.puts: list[tuple[str, str]] = []
        self.read_error = False
        self.put_error = False

    def read_exact(self, resource_type: str, resource_id: str) -> dict | None:
        if self.read_error:
            raise ReadClientError("transport failed")
        resource = self.store.get((resource_type, resource_id))
        return None if resource is None else copy.deepcopy(resource)

    def put_resource(self, resource: dict) -> None:
        if self.put_error:
            raise ReadClientError("transport failed")
        key = (str(resource["resourceType"]), str(resource["id"]))
        self.puts.append(key)
        self.store[key] = copy.deepcopy(resource)

    def transport(self):
        return ClientFHIRTransport(self)

    def get(self, path: str) -> dict:
        if self.read_error:
            raise ReadClientError("transport failed")
        if path.startswith("Patient/") and path.count("/") == 1:
            resource = self.store.get(("Patient", path.split("/", 1)[1]))
            if resource is None:
                raise ReadClientError("HTTP 404")
            return copy.deepcopy(resource)
        raise ReadClientError("unknown prepared path")

    def search(self, path: str, expected_resource_type: str) -> BoundedSearchResult:
        if self.read_error:
            return BoundedSearchResult(BoundedSearchStatus.FAILED, (), "transport failed")
        parsed = urlsplit(path)
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        selected = [
            copy.deepcopy(resource)
            for resource in self.store.values()
            if resource.get("resourceType") == expected_resource_type
            and _matches(resource, parsed.path, query)
        ]
        return BoundedSearchResult(BoundedSearchStatus.COMPLETE, tuple(selected))


def _matches(resource: dict, kind: str, query: dict[str, str]) -> bool:
    if kind == "Patient":
        system, _, value = query.get("identifier", "").partition("|")
        identifiers = resource.get("identifier")
        return isinstance(identifiers, list) and any(
            isinstance(item, dict) and item.get("system") == system and item.get("value") == value
            for item in identifiers
        )
    if kind == "Encounter":
        subject = resource.get("subject")
        reference = subject.get("reference") if isinstance(subject, dict) else None
        return reference == query.get("patient") and resource.get("status") == query.get("status")
    if kind == "Observation":
        subject = resource.get("subject")
        reference = subject.get("reference") if isinstance(subject, dict) else None
        return reference == query.get("subject") and resource.get("status") == query.get("status")
    if kind == "Appointment":
        expected = query.get("patient")
        participants = resource.get("participant")
        if not isinstance(participants, list):
            return False
        return any(
            isinstance(item, dict)
            and isinstance(item.get("actor"), dict)
            and item["actor"].get("reference") == expected
            for item in participants
        )
    return False


def _review_db(tmp_path: Path) -> Path:
    path = tmp_path / "follow-up-review.sqlite3"
    SQLiteFollowUpReviewCaseRepository(path).initialize()
    return path


def _paths(tmp_path: Path, review: Path) -> dict[str, str]:
    session = tmp_path / "human-session.sqlite3"
    knowledge = tmp_path / "institutional-knowledge.sqlite3"
    session.write_bytes(b"")
    knowledge.write_bytes(b"")
    return {
        "review_db_path": str(review.resolve()),
        "configured_review_db_path": str(review.resolve()),
        "session_db_path": str(session.resolve()),
        "knowledge_db_path": str(knowledge.resolve()),
    }


def _prepare(tmp_path: Path, review: Path, gateway: ScriptedFhir, **overrides):
    values = _paths(tmp_path, review)
    values.update(
        fhir_base_url=FHIR_URL,
        gateway=gateway,
        fixture_dir=FIXTURE_DIR,
        service_accepts_connections=lambda: False,
        clock=lambda: INSTANT,
    )
    values.update(overrides)
    return prepare.prepare_demo_review(**values)


def _rows(path: Path, sql: str, parameters: tuple = ()) -> list[sqlite3.Row]:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        return list(connection.execute(sql, parameters))
    finally:
        connection.close()


def _seed_case(repository: SQLiteFollowUpReviewCaseRepository, case_id: str, protocol_id: str, resource: str):
    reason = (
        "post_consultation_result_requires_review"
        if protocol_id == POST_CONSULTATION_RESULT_REVIEW_V1
        else REASON_MISSED
    )
    return repository.ensure(
        FollowUpReviewTrigger(
            case_id=case_id,
            protocol_id=protocol_id,
            protocol_evaluation_status="matched",
            reason_codes=(reason,),
            matched_resources=(resource,),
            review_identity=build_review_identity(case_id, protocol_id, (resource,)),
        )
    )


def _historical_dump(path: Path) -> dict[str, list[tuple]]:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        cases = connection.execute(
            """
            SELECT * FROM follow_up_review_cases
            WHERE case_id IN (?, ?, ?)
            ORDER BY case_id
            """,
            HISTORICAL_CASE_IDS,
        ).fetchall()
        ids = tuple(row["id"] for row in cases)
        marker = ",".join("?" for _ in ids)

        def children(table: str) -> list[tuple]:
            return [
                tuple(row)
                for row in connection.execute(
                    f"SELECT * FROM {table} WHERE review_case_id IN ({marker}) ORDER BY 1",
                    ids,
                )
            ]

        return {
            "cases": [tuple(row) for row in cases],
            "events": children("follow_up_review_case_events"),
            "coordination": children("follow_up_coordination_requests"),
            "attributions": children("follow_up_human_attributions"),
            "coordination_history": children("follow_up_coordination_request_events"),
        }
    finally:
        connection.close()


def _guard_other_databases(monkeypatch: pytest.MonkeyPatch, session: Path, knowledge: Path) -> None:
    real_connect = sqlite3.connect

    def connect(database, *args, **kwargs):
        if database != ":memory:":
            resolved = Path(database).resolve()
            if resolved in {session.resolve(), knowledge.resolve()}:
                raise AssertionError("preparation opened a non-review database")
        return real_connect(database, *args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", connect)


def test_first_and_second_preparation_reuse_open_cases(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    review = _review_db(tmp_path)
    paths = _paths(tmp_path, review)
    _guard_other_databases(monkeypatch, Path(paths["session_db_path"]), Path(paths["knowledge_db_path"]))
    gateway = ScriptedFhir()

    def forbidden(*_args, **_kwargs):
        raise AssertionError("agent endpoint was called")

    monkeypatch.setattr("app.followup_service.run_followup_http", forbidden)
    monkeypatch.setattr("app.missed_follow_up_service.run_missed_follow_up_http", forbidden)
    first = _prepare(tmp_path, review, gateway)
    second = _prepare(tmp_path, review, gateway)
    assert [case.case_id for case in first.cases] == ["SYN-DEMO-101", "SYN-DEMO-102"]
    assert [case.protocol_id for case in first.cases] == [
        POST_CONSULTATION_RESULT_REVIEW_V1,
        MISSED_FOLLOW_UP_REVIEW_V1,
    ]
    assert [case.status for case in first.cases] == ["open", "open"]
    assert [case.review_case_id for case in second.cases] == [case.review_case_id for case in first.cases]
    stored = _rows(review, "SELECT case_id, status, version, outcome FROM follow_up_review_cases ORDER BY case_id")
    assert [(row["case_id"], row["status"], row["version"], row["outcome"]) for row in stored] == [
        ("SYN-DEMO-101", "open", 1, None),
        ("SYN-DEMO-102", "open", 1, None),
    ]
    assert len(_rows(review, "SELECT event_id FROM follow_up_review_case_events")) == 2
    assert _rows(review, "SELECT id FROM follow_up_coordination_requests") == []
    assert _rows(review, "SELECT attribution_id FROM follow_up_human_attributions") == []
    assert gateway.puts == [
        ("Patient", "syn-demo-patient-101"),
        ("Encounter", "syn-demo-enc-101"),
        ("Observation", "syn-demo-obs-101"),
        ("Patient", "syn-demo-patient-102"),
        ("Appointment", "syn-demo-noshow-102"),
    ] * 2


def test_closed_case_aborts_without_reopening(tmp_path: Path):
    review = _review_db(tmp_path)
    gateway = ScriptedFhir()
    created = _prepare(tmp_path, review, gateway)
    repository = SQLiteFollowUpReviewCaseRepository(review)
    repository.close(
        created.cases[0].review_case_id,
        expected_version=1,
        outcome=ReviewOutcome.REVIEW_COMPLETED_NO_OPERATIONAL_ACTION,
    )
    before = _rows(review, "SELECT * FROM follow_up_review_cases ORDER BY case_id")
    events_before = len(_rows(review, "SELECT event_id FROM follow_up_review_case_events"))
    with pytest.raises(prepare.DemoPreparationAborted) as caught:
        _prepare(tmp_path, review, gateway)
    assert caught.value.reason == "review_case_closed"
    assert "explicit reset is required" in str(caught.value)
    after = _rows(review, "SELECT * FROM follow_up_review_cases ORDER BY case_id")
    assert [tuple(row) for row in after] == [tuple(row) for row in before]
    assert len(_rows(review, "SELECT event_id FROM follow_up_review_case_events")) == events_before
    assert len(gateway.puts) == 5


def test_wrong_protocol_aborts_without_writing(tmp_path: Path):
    review = _review_db(tmp_path)
    repository = SQLiteFollowUpReviewCaseRepository(review)
    seeded = _seed_case(
        repository,
        "SYN-DEMO-101",
        MISSED_FOLLOW_UP_REVIEW_V1,
        "Appointment/not-the-demo-appointment",
    )
    gateway = ScriptedFhir()
    with pytest.raises(prepare.DemoPreparationAborted) as caught:
        _prepare(tmp_path, review, gateway)
    assert caught.value.reason == "review_protocol_mismatch"
    stored = _rows(review, "SELECT id, case_id, protocol_id, status FROM follow_up_review_cases")
    assert [(row["id"], row["case_id"], row["protocol_id"], row["status"]) for row in stored] == [
        (seeded.id, "SYN-DEMO-101", MISSED_FOLLOW_UP_REVIEW_V1, "open")
    ]
    assert gateway.puts == []


def test_unmatched_evaluation_creates_no_review_case(tmp_path: Path):
    review = _review_db(tmp_path)
    fixture_dir = tmp_path / "fixtures"
    shutil.copytree(FIXTURE_DIR, fixture_dir, ignore=shutil.ignore_patterns("*.py"))
    appointment = json.loads((fixture_dir / "syn-demo-noshow-102.json").read_text(encoding="utf-8"))
    appointment["status"] = "cancelled"
    (fixture_dir / "syn-demo-noshow-102.json").write_text(json.dumps(appointment), encoding="utf-8")
    gateway = ScriptedFhir()
    with pytest.raises(prepare.DemoPreparationAborted) as caught:
        _prepare(tmp_path, review, gateway, fixture_dir=fixture_dir)
    assert caught.value.reason == "evaluation_not_matched"
    assert _rows(review, "SELECT id FROM follow_up_review_cases") == []
    assert len(gateway.puts) == 5


def test_foreign_fhir_id_is_not_overwritten(tmp_path: Path):
    review = _review_db(tmp_path)
    gateway = ScriptedFhir()
    foreign = {
        "resourceType": "Patient",
        "id": "syn-demo-patient-101",
        "identifier": [
            {"system": "https://lab.local/followup-case", "value": "SYN-FOLLOWUP-006"}
        ],
    }
    gateway.store[("Patient", "syn-demo-patient-101")] = copy.deepcopy(foreign)
    with pytest.raises(prepare.DemoPreparationAborted) as caught:
        _prepare(tmp_path, review, gateway)
    assert caught.value.reason == "fhir_ownership_rejected"
    assert gateway.store[("Patient", "syn-demo-patient-101")] == foreign
    assert gateway.puts == []
    assert _rows(review, "SELECT id FROM follow_up_review_cases") == []


def test_fhir_connection_error_aborts_before_put(tmp_path: Path):
    review = _review_db(tmp_path)
    gateway = ScriptedFhir()
    gateway.read_error = True
    with pytest.raises(prepare.DemoPreparationAborted) as caught:
        _prepare(tmp_path, review, gateway)
    assert caught.value.reason == "fhir_connection_error"
    assert gateway.puts == []
    assert _rows(review, "SELECT id FROM follow_up_review_cases") == []


@pytest.mark.parametrize(
    ("path_kind", "reason"),
    [
        ("relative", "review_db_path_invalid"),
        ("missing", "review_db_missing"),
        ("session", "session_database"),
        ("knowledge", "knowledge_database"),
        ("unconfigured", "review_db_not_configured"),
    ],
)
def test_invalid_review_database_path(tmp_path: Path, path_kind: str, reason: str):
    review = _review_db(tmp_path)
    gateway = ScriptedFhir()
    overrides: dict = {}
    if path_kind == "relative":
        overrides["review_db_path"] = "follow-up-review.sqlite3"
    elif path_kind == "missing":
        overrides["review_db_path"] = str(tmp_path / "missing.sqlite3")
    elif path_kind == "session":
        overrides["review_db_path"] = overrides["session_db_path"] = str((tmp_path / "human-session.sqlite3").resolve())
        (tmp_path / "human-session.sqlite3").write_bytes(b"")
    elif path_kind == "knowledge":
        knowledge = tmp_path / "institutional-knowledge.sqlite3"
        knowledge.write_bytes(b"")
        overrides["review_db_path"] = overrides["knowledge_db_path"] = str(knowledge.resolve())
    else:
        other = tmp_path / "other-review.sqlite3"
        other.write_bytes(b"")
        overrides["configured_review_db_path"] = str(other.resolve())
    with pytest.raises(prepare.DemoPreparationAborted) as caught:
        _prepare(tmp_path, review, gateway, **overrides)
    assert caught.value.reason == reason
    assert gateway.puts == []


@pytest.mark.parametrize("version", [3, 5])
def test_incompatible_schema_is_left_unchanged(tmp_path: Path, version: int):
    review = _review_db(tmp_path)
    connection = sqlite3.connect(review)
    connection.execute(f"PRAGMA user_version = {int(version)}")
    connection.commit()
    connection.close()
    gateway = ScriptedFhir()
    with pytest.raises(prepare.DemoPreparationAborted) as caught:
        _prepare(tmp_path, review, gateway)
    assert caught.value.reason == "schema_incompatible"
    assert sqlite3.connect(review).execute("PRAGMA user_version").fetchone()[0] == version
    assert gateway.puts == []


def test_active_service_aborts_before_opening_sqlite(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    review = _review_db(tmp_path)

    def connect(*_args, **_kwargs):
        raise AssertionError("sqlite opened")

    monkeypatch.setattr(sqlite3, "connect", connect)
    with pytest.raises(prepare.DemoPreparationAborted) as caught:
        _prepare(tmp_path, review, ScriptedFhir(), service_accepts_connections=lambda: True)
    assert caught.value.reason == "service_accepting_connections"


def test_exclusive_lock_failure_aborts(tmp_path: Path):
    review = _review_db(tmp_path)
    holder = sqlite3.connect(review, timeout=0.1, isolation_level=None)
    holder.execute("BEGIN IMMEDIATE")
    gateway = ScriptedFhir()
    try:
        with pytest.raises(prepare.DemoPreparationAborted) as caught:
            _prepare(tmp_path, review, gateway, busy_timeout_ms=200)
        assert caught.value.reason == "exclusive_lock_unavailable"
    finally:
        holder.rollback()
        holder.close()
    assert gateway.puts == []
    assert _rows(review, "SELECT id FROM follow_up_review_cases") == []


def test_historical_cases_stay_unchanged(tmp_path: Path):
    review = _review_db(tmp_path)
    repository = SQLiteFollowUpReviewCaseRepository(review)
    _seed_case(repository, "SYN-FOLLOWUP-006", POST_CONSULTATION_RESULT_REVIEW_V1, "Encounter/historical-enc-006")
    closed = _seed_case(
        repository,
        "SYN-FOLLOWUP-008",
        POST_CONSULTATION_RESULT_REVIEW_V1,
        "Observation/historical-obs-008",
    )
    _seed_case(repository, "SYN-FOLLOWUP-012", MISSED_FOLLOW_UP_REVIEW_V1, "Appointment/historical-appointment-012")
    snapshot = DevelopmentPrincipalSnapshot(
        principal_id="lab-reviewer",
        authenticator_id=DEVELOPMENT_AUTHENTICATOR_V1,
        session_id=str(uuid.uuid4()),
    )
    repository.close(
        closed.id,
        expected_version=1,
        outcome=ReviewOutcome.FOLLOW_UP_COORDINATION_PLANNED,
        attribution=snapshot,
    )
    repository.ensure_follow_up_coordination_request(closed.id, attribution=snapshot)
    before = _historical_dump(review)
    report = _prepare(tmp_path, review, ScriptedFhir())
    assert _historical_dump(review) == before
    assert {case.case_id for case in report.cases} == {"SYN-DEMO-101", "SYN-DEMO-102"}
    demo_ids = _rows(
        review,
        "SELECT id FROM follow_up_review_cases WHERE case_id IN ('SYN-DEMO-101', 'SYN-DEMO-102')",
    )
    assert len(demo_ids) == 2
    placeholders = ",".join("?" for _ in demo_ids)
    parameters = tuple(row["id"] for row in demo_ids)
    assert _rows(
        review,
        f"SELECT id FROM follow_up_coordination_requests WHERE review_case_id IN ({placeholders})",
        parameters,
    ) == []
    assert _rows(
        review,
        f"SELECT attribution_id FROM follow_up_human_attributions WHERE review_case_id IN ({placeholders})",
        parameters,
    ) == []


def test_preparation_does_not_call_gemini_or_expand_the_request_allowlist():
    source = PREPARE_PATH.read_text(encoding="utf-8")
    assert "google.genai" not in source
    assert "langgraph_gemini" not in source
    assert "generate_content" not in source
    assert "GEMINI_API_KEY" not in source
    assert "run_followup_http" not in source
    assert "run_missed_follow_up_http" not in source
    assert "FollowUpRequest" not in source
    assert "load-synthetic-patients" not in source
    assert "glob(" not in source
    assert "SYN-DEMO-101" not in CASE_IDS
    assert "SYN-DEMO-102" not in CASE_IDS
    with pytest.raises(ValidationError):
        FollowUpRequest.model_validate({"caseId": "SYN-DEMO-101"})


def test_remote_fhir_url_and_historical_fixture_directory_are_rejected(tmp_path: Path):
    review = _review_db(tmp_path)
    gateway = ScriptedFhir()
    with pytest.raises(prepare.DemoPreparationAborted) as remote:
        _prepare(tmp_path, review, gateway, fhir_base_url="http://example.com/fhir")
    assert remote.value.reason == "fhir_base_url_not_loopback"
    with pytest.raises(prepare.DemoPreparationAborted) as historical:
        _prepare(tmp_path, review, gateway, fixture_dir=REPO_ROOT / "scripts" / "fhir")
    assert historical.value.reason == "fixture_directory_rejected"
    assert gateway.puts == []
    with pytest.raises(prepare.DemoPreparationAborted):
        prepare.LoopbackFhirGateway("https://example.com/fhir")


class _PatientHttp:
    def __init__(self, status: int, payload=None, *, broken: bool = False) -> None:
        self.status_code = status
        self._payload = payload
        self._broken = broken

    def json(self):
        if self._broken:
            raise ValueError("not json")
        return self._payload


class _ExactMiss:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def read_exact(self, resource_type: str, resource_id: str):
        self.calls.append((resource_type, resource_id))
        from app.langgraph_fhir_client import ExactResourceNotFound

        raise ExactResourceNotFound()


def _patient_body(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _replace_with_patient_http(answers: dict[str, object]):
    requested: list[str] = []
    reader = _ExactMiss()

    def patient_get(url: str, accept: str):
        requested.append(url)
        assert accept
        patient_id = url.rsplit("/", 1)[-1]
        answer = answers[patient_id]
        if isinstance(answer, BaseException):
            raise answer
        return answer

    inner = prepare.LoopbackFhirGateway(FHIR_URL, patient_get=patient_get, reader=reader)
    puts: list[tuple[str, str]] = []

    class _Gateway:
        def read_exact(self, resource_type: str, resource_id: str):
            return inner.read_exact(resource_type, resource_id)

        def put_resource(self, resource: dict) -> None:
            puts.append((str(resource["resourceType"]), str(resource["id"])))

    return _Gateway(), puts, requested, reader


def test_absent_demo_patients_allow_later_creation():
    gateway, puts, requested, reader = _replace_with_patient_http(
        {
            "syn-demo-patient-101": _PatientHttp(404),
            "syn-demo-patient-102": _PatientHttp(404),
        }
    )
    prepare._replace_owned_resources(gateway, prepare._load_fixtures(FIXTURE_DIR))
    assert puts == [
        ("Patient", "syn-demo-patient-101"),
        ("Encounter", "syn-demo-enc-101"),
        ("Observation", "syn-demo-obs-101"),
        ("Patient", "syn-demo-patient-102"),
        ("Appointment", "syn-demo-noshow-102"),
    ]
    assert requested == [
        f"{FHIR_URL}/Patient/syn-demo-patient-101",
        f"{FHIR_URL}/Patient/syn-demo-patient-102",
    ]
    assert ("Patient", "syn-demo-patient-101") not in reader.calls
    assert ("Encounter", "syn-demo-enc-101") in reader.calls


def test_owned_demo_patients_remain_replaceable():
    gateway, puts, requested, _reader = _replace_with_patient_http(
        {
            "syn-demo-patient-101": _PatientHttp(200, _patient_body("syn-demo-patient-101.json")),
            "syn-demo-patient-102": _PatientHttp(200, _patient_body("syn-demo-patient-102.json")),
        }
    )
    prepare._replace_owned_resources(gateway, prepare._load_fixtures(FIXTURE_DIR))
    assert [item[0] for item in puts].count("Patient") == 2
    assert len(requested) == 2


def test_foreign_demo_patient_identifier_is_not_overwritten():
    foreign = _patient_body("syn-demo-patient-102.json")
    foreign["identifier"] = [
        {"system": "https://lab.local/followup-case", "value": "SYN-OTHER-999"}
    ]
    gateway, puts, _requested, _reader = _replace_with_patient_http(
        {
            "syn-demo-patient-101": _PatientHttp(200, _patient_body("syn-demo-patient-101.json")),
            "syn-demo-patient-102": _PatientHttp(200, foreign),
        }
    )
    with pytest.raises(prepare.DemoPreparationAborted) as caught:
        prepare._replace_owned_resources(gateway, prepare._load_fixtures(FIXTURE_DIR))
    assert caught.value.reason == "fhir_ownership_rejected"
    assert puts == []


@pytest.mark.parametrize(
    "payload",
    [
        {"resourceType": "Patient", "id": "syn-demo-patient-999"},
        {"resourceType": "OperationOutcome", "id": "syn-demo-patient-101"},
        ["Patient"],
        {
            "resourceType": "Patient",
            "id": "syn-demo-patient-101",
            "identifier": [
                {"system": "https://lab.local/followup-case", "value": "SYN-DEMO-101"}
            ],
            "link": [{"other": {"reference": "Patient/someone-else"}}],
        },
    ],
)
def test_ambiguous_demo_patient_is_not_overwritten(payload):
    gateway, puts, _requested, _reader = _replace_with_patient_http(
        {
            "syn-demo-patient-101": _PatientHttp(200, payload),
            "syn-demo-patient-102": _PatientHttp(404),
        }
    )
    with pytest.raises(prepare.DemoPreparationAborted) as caught:
        prepare._replace_owned_resources(gateway, prepare._load_fixtures(FIXTURE_DIR))
    assert caught.value.reason == "fhir_ownership_rejected"
    assert puts == []


def test_unreadable_demo_patient_body_is_not_overwritten():
    gateway, puts, _requested, _reader = _replace_with_patient_http(
        {
            "syn-demo-patient-101": _PatientHttp(200, broken=True),
            "syn-demo-patient-102": _PatientHttp(404),
        }
    )
    with pytest.raises(prepare.DemoPreparationAborted) as caught:
        prepare._replace_owned_resources(gateway, prepare._load_fixtures(FIXTURE_DIR))
    assert caught.value.reason == "fhir_ownership_rejected"
    assert puts == []


@pytest.mark.parametrize("status", [201, 302, 500])
def test_unexpected_demo_patient_status_aborts(status: int):
    gateway, puts, _requested, _reader = _replace_with_patient_http(
        {
            "syn-demo-patient-101": _PatientHttp(status),
            "syn-demo-patient-102": _PatientHttp(404),
        }
    )
    with pytest.raises(prepare.DemoPreparationAborted) as caught:
        prepare._replace_owned_resources(gateway, prepare._load_fixtures(FIXTURE_DIR))
    assert caught.value.reason == "fhir_unexpected_response"
    assert puts == []


@pytest.mark.parametrize(
    "failure",
    [TimeoutError("timed out"), ConnectionError("connection failed")],
)
def test_demo_patient_timeout_or_connection_failure_aborts(failure: BaseException):
    gateway, puts, _requested, _reader = _replace_with_patient_http(
        {
            "syn-demo-patient-101": failure,
            "syn-demo-patient-102": _PatientHttp(404),
        }
    )
    with pytest.raises(prepare.DemoPreparationAborted) as caught:
        prepare._replace_owned_resources(gateway, prepare._load_fixtures(FIXTURE_DIR))
    assert caught.value.reason == "fhir_connection_error"
    assert puts == []


def test_httpx_demo_patient_transport_failures_abort():
    import httpx

    for failure in (httpx.TimeoutException("timed out"), httpx.ConnectError("connection failed")):
        gateway, puts, _requested, _reader = _replace_with_patient_http(
            {
                "syn-demo-patient-101": failure,
                "syn-demo-patient-102": _PatientHttp(404),
            }
        )
        with pytest.raises(prepare.DemoPreparationAborted) as caught:
            prepare._replace_owned_resources(gateway, prepare._load_fixtures(FIXTURE_DIR))
        assert caught.value.reason == "fhir_connection_error"
        assert puts == []


def test_demo_patient_read_rejects_any_other_patient_id():
    requested: list[str] = []

    def patient_get(url: str, accept: str):
        requested.append(url)
        return _PatientHttp(200, _patient_body("syn-demo-patient-101.json"))

    gateway = prepare.LoopbackFhirGateway(FHIR_URL, patient_get=patient_get, reader=_ExactMiss())
    with pytest.raises(prepare.DemoPreparationAborted) as caught:
        gateway.read_exact("Patient", "SYN-PATIENT-006")
    assert caught.value.reason == "fhir_ownership_rejected"
    assert requested == []


def test_service_read_exact_allowlist_still_excludes_patient():
    from app.langgraph_fhir_hapi import _EXACT_RESOURCE_TYPES

    assert _EXACT_RESOURCE_TYPES == frozenset({"Encounter", "Observation", "Appointment"})
    source = (REPO_ROOT / "services" / "ai-service" / "app" / "langgraph_fhir_hapi.py").read_text(
        encoding="utf-8"
    )
    assert '_EXACT_RESOURCE_TYPES = frozenset({"Encounter", "Observation", "Appointment"})' in source
    utility = PREPARE_PATH.read_text(encoding="utf-8")
    assert "_EXACT_RESOURCE_TYPES" not in utility
    assert "_DEMO_PATIENT_READS = frozenset" in utility


def test_tcp_probe_reports_an_open_port_and_an_unanswered_port():
    with socket.socket() as listening:
        listening.bind(("127.0.0.1", 0))
        listening.listen(1)
        open_port = listening.getsockname()[1]
        closed = socket.socket()
        closed.bind(("127.0.0.1", 0))
        closed_port = closed.getsockname()[1]
        closed.close()
        assert prepare.tcp_accepts("127.0.0.1", open_port, timeout=0.5) is True
        assert prepare.tcp_accepts("127.0.0.1", closed_port, timeout=0.2) is False
