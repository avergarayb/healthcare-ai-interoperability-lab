"""Presentation tests for the synthetic human review client."""

from __future__ import annotations

import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import unquote, urlencode

import pytest
from fastapi.testclient import TestClient

from app.clinical_review_context import (
    BooleanContent,
    CodedContent,
    CodingEntry,
    ComponentsContent,
    ComponentContent,
    IntegerContent,
    NotProjectedContent,
    QuantityContent,
    QuantityFields,
    RangeContent,
    StringContent,
)
from app.config import Settings
from app.human_development_auth import SESSION_COOKIE
from app.human_session import HumanSessionService
from app.human_session_sqlite import SQLiteHumanSessionRepository
from app.followup_coordination_action import FollowUpCoordinationActionService
from app.followup_review import (
    FollowUpReviewCaseService,
    ReviewCaseConflict,
    ReviewCaseStatus,
    ReviewOutcome,
)
from app.human_review_client import (
    FORM_TTL_SECONDS,
    MSG_CHANGED,
    MSG_CLOSE_INVALID,
    MSG_CODE_HIDDEN,
    MSG_CONTEXT_UNAVAILABLE,
    MSG_CURSOR,
    MSG_EMPTY,
    MSG_ENCOUNTER_MISSING,
    MSG_FORM_INVALID,
    MSG_NOT_CONFIGURED,
    MSG_INVALID_LINK,
    MSG_NOT_FOUND,
    MSG_OBSERVATION_MISSING,
    MSG_ORIGIN_INVALID,
    MSG_REVIEW_UNAVAILABLE,
    MSG_VALUE_HIDDEN,
    form_token_is_valid,
    issue_form_token,
    render_observation_value,
    _readable_utc,
)
from app.langgraph_fhir_client import BoundedSearchResult, BoundedSearchStatus, CASE_IDENTIFIER_SYSTEM, ReadClientError
from app.main import app, get_settings
from app.missed_follow_up_review import MISSED_FOLLOW_UP_REVIEW_V1
from app.post_consultation_review import (
    POST_CONSULTATION_RESULT_REVIEW_V1,
    ProtocolEvaluationStatus,
    ProtocolReviewResult,
)
from app.followup_review_sqlite import SQLiteFollowUpReviewCaseRepository


SERVICE_TOKEN = "synthetic-service-token-a"
SIGNING_SECRET = "synthetic-form-signing-secret-b"
DEV_SECRET = "development-secret-value-32chars-min"
TOKEN_SESSION = "11111111-1111-4111-8111-111111111111"
CASE = "SYN-FOLLOWUP-008"
PATIENT = "SYN-PATIENT-008"
ORIGIN = {"origin": "http://127.0.0.1"}
NOW = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)


class Clock:
    def __init__(self) -> None:
        self.value = NOW

    def __call__(self):
        current = self.value
        self.value += timedelta(seconds=1)
        return current


def _settings() -> Settings:
    return Settings(
        model_boundary_base_url="http://model-boundary.test",
        model_boundary_path="/api/model-boundary/v1",
        model_boundary_timeout_seconds=5,
        model_boundary_service_token=SERVICE_TOKEN,
        human_review_form_signing_secret=SIGNING_SECRET,
        host="127.0.0.1",
        port=8090,
        followup_agent_enabled=True,
        ai_review_db_path="unused-by-explicit-test-repository.sqlite3",
        human_session_db_path="unused-human-session-overridden-by-state.sqlite3",
        human_review_development_auth_enabled=True,
        human_review_development_auth_secret=DEV_SECRET,
        human_review_development_principal_id="lab-reviewer",
        human_review_development_principal_display_name="Lab reviewer",
    )


def _protocol(suffix: str = "008") -> ProtocolReviewResult:
    return ProtocolReviewResult(
        id=POST_CONSULTATION_RESULT_REVIEW_V1,
        evaluation_status=ProtocolEvaluationStatus.MATCHED,
        reason_codes=("post_consultation_result_requires_review",),
        matched_resources=(f"Encounter/encounter-{suffix}", f"Observation/observation-{suffix}"),
        human_review_status="required",
        human_review_reason="deterministic_post_consultation_protocol_match",
        action_status="proposed",
        action_type="review_follow_up_case",
    )


def _repository(tmp_path, name="review.sqlite3"):
    repository = SQLiteFollowUpReviewCaseRepository(tmp_path / name, clock=Clock())
    repository.initialize()
    return repository


def _create(repository, *, case_id=CASE, suffix="008"):
    case = FollowUpReviewCaseService(repository).ensure_for_protocol(case_id, _protocol(suffix))
    assert case is not None
    return case


class ScriptedFhir:
    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.encounter = {
            "resourceType": "Encounter",
            "id": "encounter-008",
            "status": "finished",
            "subject": {"reference": f"Patient/{PATIENT}"},
            "period": {"start": "2026-09-30T11:00:00Z", "end": "2026-09-30T11:30:00Z"},
        }
        self.observation = {
            "resourceType": "Observation",
            "id": "observation-008",
            "status": "final",
            "subject": {"reference": f"Patient/{PATIENT}"},
            "encounter": {"reference": "Encounter/encounter-008"},
            "issued": "2026-09-30T11:20:00Z",
            "code": {"coding": [{"system": "http://loinc.org", "code": "1234-5", "display": "Synthetic"}], "text": "Synthetic result"},
            "valueString": "synthetic-result",
        }
        self.appointments = [_appointment("booked", "2099-01-01T00:00:00Z")]
        self.exact_appointments: list[dict] = []
        self.patient_status = BoundedSearchStatus.COMPLETE
        self.appointment_status = BoundedSearchStatus.COMPLETE
        self.missing: set[str] = set()

    def search(self, path: str, expected_resource_type: str):
        self.calls.append(("search", expected_resource_type, path))
        if expected_resource_type == "Patient":
            case_id = CASE
            if "identifier=" in path:
                token = unquote(path.split("identifier=", 1)[1].split("&", 1)[0])
                if "|" in token:
                    case_id = token.split("|", 1)[1]
            patient = {
                "resourceType": "Patient",
                "id": PATIENT,
                "identifier": [{"system": CASE_IDENTIFIER_SYSTEM, "value": case_id}],
            }
            return BoundedSearchResult(self.patient_status, (patient,))
        return BoundedSearchResult(self.appointment_status, tuple(self.appointments))

    def read_exact(self, resource_type: str, resource_id: str) -> dict:
        self.calls.append(("exact", resource_type, resource_id))
        if resource_type in self.missing or resource_id in self.missing:
            from app.langgraph_fhir_client import ExactResourceNotFound

            raise ExactResourceNotFound()
        if resource_type == "Encounter":
            return dict(self.encounter)
        if resource_type == "Observation":
            return dict(self.observation)
        if resource_type == "Appointment":
            for item in (*self.exact_appointments, *self.appointments):
                if item.get("id") == resource_id:
                    return dict(item)
            from app.langgraph_fhir_client import ExactResourceNotFound

            raise ExactResourceNotFound()
        raise AssertionError(resource_type)


def _appointment(status: str, start: str, appointment_id: str = "appointment-008") -> dict:
    return {
        "resourceType": "Appointment",
        "id": appointment_id,
        "status": status,
        "start": start,
        "participant": [{"actor": {"reference": f"Patient/{PATIENT}"}, "status": "accepted"}],
    }


@pytest.fixture(autouse=True)
def _clean_state():
    app.dependency_overrides.clear()
    for name in (
        "followup_review_repository",
        "clinical_context_fhir_client",
        "human_session_repository",
        "human_session_clock",
    ):
        if hasattr(app.state, name):
            delattr(app.state, name)
    yield
    app.dependency_overrides.clear()
    for name in (
        "followup_review_repository",
        "clinical_context_fhir_client",
        "human_session_repository",
        "human_session_clock",
    ):
        if hasattr(app.state, name):
            delattr(app.state, name)


def _prepare_session(repository) -> None:
    path = getattr(repository, "database_path", None)
    if path is None:
        path = getattr(getattr(repository, "inner", None), "database_path", None)
    directory = Path(path).parent if path is not None else Path(tempfile.mkdtemp(prefix="review-session-"))
    store = SQLiteHumanSessionRepository(directory / "human-session.sqlite3")
    store.initialize()
    app.state.human_session_repository = store


def _login(client: TestClient) -> None:
    response = client.post(
        "/review-login",
        content=urlencode({"developmentSecret": DEV_SECRET}),
        headers={**ORIGIN, "content-type": "application/x-www-form-urlencoded"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text


def _session_id(client: TestClient) -> str:
    token = client.cookies.get(SESSION_COOKIE)
    assert token
    return HumanSessionService(
        app.state.human_session_repository,
        clock=lambda: datetime.now(timezone.utc),
    ).resolve(token).session_id


def _client(repository, fhir: ScriptedFhir | None = None) -> TestClient:
    app.state.followup_review_repository = repository
    if fhir is not None:
        app.state.clinical_context_fhir_client = lambda: fhir
    _prepare_session(repository)
    app.dependency_overrides[get_settings] = _settings
    client = TestClient(app, base_url="http://127.0.0.1")
    _login(client)
    return client


def _fields(html: str) -> dict[str, str]:
    fields = {}
    for name in ("expectedVersion", "formToken", "formExpiry"):
        marker = f'name="{name}" value="'
        start = html.index(marker) + len(marker)
        fields[name] = html[start:html.index('"', start)]
    return fields


def _post_close(client: TestClient, case_id: str, html: str, outcome: str, **overrides):
    fields = _fields(html)
    payload = {
        "outcome": outcome,
        "expectedVersion": fields["expectedVersion"],
        "formToken": fields["formToken"],
        "formExpiry": fields["formExpiry"],
    }
    payload.update(overrides)
    return client.post(
        f"/review-cases/{case_id}/close",
        content=urlencode(payload),
        headers={**ORIGIN, "content-type": "application/x-www-form-urlencoded"},
        follow_redirects=False,
    )


def test_queue_lists_open_cases_and_hides_patient_identity(tmp_path):
    repository = _repository(tmp_path)
    case = _create(repository)
    response = _client(repository).get("/review-cases")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert case.case_id in response.text
    assert case.protocol_id in response.text
    assert ">open<" in response.text
    assert f'href="/review-cases/{case.id}"' in response.text
    assert "<th>Caso</th>" in response.text
    assert "no es la identidad del paciente" in response.text
    assert PATIENT not in response.text
    assert SIGNING_SECRET not in response.text
    assert SIGNING_SECRET not in response.headers.values()


def test_empty_queue_is_explicit(tmp_path):
    response = _client(_repository(tmp_path)).get("/review-cases")
    assert MSG_EMPTY in response.text


def test_queue_cursor_links_to_the_next_page(tmp_path):
    repository = _repository(tmp_path)
    for index in range(26):
        _create(repository, case_id=f"SYN-FOLLOWUP-{index:03d}", suffix=f"{index:03d}")
    first = _client(repository).get("/review-cases")
    assert "Casos más antiguos" in first.text
    href = first.text.split('href="/review-cases?cursor=', 1)[1].split('"', 1)[0]
    second = _client(repository).get(f"/review-cases?cursor={href}")
    assert second.status_code == 200
    assert "SYN-FOLLOWUP-000" not in second.text
    assert "SYN-FOLLOWUP-025" in second.text


def test_invalid_cursor_and_unavailable_queue(tmp_path):
    repository = _repository(tmp_path)
    invalid = _client(repository).get("/review-cases?cursor=not-a-cursor")
    assert invalid.status_code == 422
    assert MSG_CURSOR in invalid.text
    unavailable = _client(None).get("/review-cases")
    assert unavailable.status_code == 503
    assert MSG_REVIEW_UNAVAILABLE in unavailable.text


def test_open_case_page_separates_sections_and_renders_context(tmp_path):
    repository = _repository(tmp_path)
    case = _create(repository)
    fhir = ScriptedFhir()
    fhir.observation["valueString"] = "<b>unsafe</b>"
    response = _client(repository, fhir).get(f"/review-cases/{case.id}")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    for heading in (
        "Resumen del caso",
        "Por qué está en revisión",
        "Contexto clínico actual",
        "Historial operativo",
        "Resultado operativo",
    ):
        assert f"<h2>{heading}</h2>" in response.text
    assert "No vuelve a ejecutar la regla que creó el caso." in response.text
    assert "Quedó registrado un resultado posterior a la consulta" in response.text
    visible, technical = response.text.split("<details>", 1)
    assert "Technical provenance" not in response.text
    assert "Encounter/encounter-008" not in visible
    assert "Encounter/encounter-008" in technical
    assert "&lt;b&gt;unsafe&lt;/b&gt;" in response.text
    assert "<b>unsafe</b>" not in response.text
    assert "finished" in visible
    assert "Próxima y confirmada" in response.text
    assert 'value="follow_up_coordination_planned"' in response.text
    assert "No es un diagnóstico" in response.text
    assert PATIENT not in response.text
    assert "resourceType" not in response.text
    assert SIGNING_SECRET not in response.text


def test_missing_resources_hidden_values_and_no_appointments(tmp_path):
    repository = _repository(tmp_path)
    case = _create(repository)
    fhir = ScriptedFhir()
    fhir.missing.add("Encounter")
    missing_encounter = _client(repository, fhir).get(f"/review-cases/{case.id}")
    assert MSG_ENCOUNTER_MISSING in missing_encounter.text
    fhir = ScriptedFhir()
    fhir.missing.add("Observation")
    missing_observation = _client(repository, fhir).get(f"/review-cases/{case.id}")
    assert MSG_OBSERVATION_MISSING in missing_observation.text
    fhir = ScriptedFhir()
    fhir.observation = {
        "resourceType": "Observation",
        "id": "observation-008",
        "status": "final",
        "subject": {"reference": f"Patient/{PATIENT}"},
        "encounter": {"reference": "Encounter/encounter-008"},
        "code": {"text": "   "},
        "valueDateTime": "2026-09-30T00:00:00Z",
    }
    hidden = _client(repository, fhir).get(f"/review-cases/{case.id}")
    assert MSG_CODE_HIDDEN in hidden.text
    assert MSG_VALUE_HIDDEN in hidden.text
    assert "valueDateTime" not in hidden.text
    fhir = ScriptedFhir()
    fhir.appointments = []
    none = _client(repository, fhir).get(f"/review-cases/{case.id}")
    assert "No se obtuvo ninguna cita." in none.text


@pytest.mark.parametrize(
    ("status", "start", "label"),
    [
        ("booked", "2099-01-01T00:00:00Z", "Próxima y confirmada"),
        ("proposed", "2099-01-01T00:00:00Z", "Próxima y no confirmada"),
        ("cancelled", "2099-01-01T00:00:00Z", "Cancelada"),
        ("fulfilled", "2020-01-01T00:00:00Z", "Pasada"),
        ("noshow", "2099-01-01T00:00:00Z", "Estado operativo de la cita no clasificado"),
    ],
)
def test_appointment_classifications_stay_operational(tmp_path, status, start, label):
    repository = _repository(tmp_path)
    case = _create(repository)
    fhir = ScriptedFhir()
    fhir.appointments = [_appointment(status, start)]
    response = _client(repository, fhir).get(f"/review-cases/{case.id}")
    assert label in response.text
    assert "Other appointment status" not in response.text
    assert "Cita que originó el caso" not in response.text
    lowered = response.text.lower()
    for banned in ("clinically", "clínicamente", "reschedul", "reprogram"):
        assert banned not in lowered
    if status == "noshow":
        visible, technical = response.text.split("<details>", 1)
        assert ">OTHER<" in technical
        assert ">noshow<" in technical
        assert ">OTHER<" not in visible


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        (QuantityContent(status="available", kind="quantity", value=1.5, comparator="<", unit="mg"), "&lt; 1.5 mg"),
        (CodedContent(status="available", kind="coded", coding=[CodingEntry(code="1234-5")], text=None), "1234-5"),
        (StringContent(status="available", kind="string", value="synthetic"), "synthetic"),
        (BooleanContent(status="available", kind="boolean", value=False), "false"),
        (IntegerContent(status="available", kind="integer", value=0), "0"),
        (
            RangeContent(
                status="available",
                kind="range",
                low=QuantityFields(value=1),
                high=QuantityFields(value=2),
            ),
            "Lower bound",
        ),
        (
            ComponentsContent(
                status="available",
                kind="components",
                components=[
                    ComponentContent(
                        code={"status": "available", "coding": [{"code": "a"}]},
                        value={"status": "available", "kind": "integer", "value": 2},
                    )
                ],
            ),
            "a",
        ),
        (NotProjectedContent(status="not_projected"), MSG_VALUE_HIDDEN),
    ],
)
def test_every_observation_kind_renders_without_interpretation(content, expected):
    rendered = render_observation_value(content)
    assert expected in rendered
    for banned in ("normal", "abnormal", "urgent", "safe", "unsafe"):
        assert banned not in rendered.lower()


def test_context_unavailable_keeps_the_close_form(tmp_path):
    repository = _repository(tmp_path)
    case = _create(repository)

    def fail():
        raise ReadClientError("secret-fhir-failure")

    client = _client(repository)
    app.state.clinical_context_fhir_client = fail
    response = client.get(f"/review-cases/{case.id}")
    assert MSG_CONTEXT_UNAVAILABLE in response.text
    assert "Cerrar la revisión" in response.text
    assert "secret-fhir-failure" not in response.text
    assert "Resumen del caso" in response.text


def test_invalid_and_missing_case(tmp_path):
    repository = _repository(tmp_path)
    client = _client(repository)
    invalid = client.get("/review-cases/not-a-uuid")
    missing = client.get("/review-cases/00000000-0000-4000-8000-000000000000")
    assert invalid.status_code == 422
    assert MSG_INVALID_LINK in invalid.text
    assert missing.status_code == 404
    assert MSG_NOT_FOUND in missing.text


def test_close_success_then_closed_page_and_queue(tmp_path):
    repository = _repository(tmp_path)
    case = _create(repository)
    fhir = ScriptedFhir()
    client = _client(repository, fhir)
    page = client.get(f"/review-cases/{case.id}")
    closed = _post_close(client, case.id, page.text, "follow_up_coordination_planned")
    assert closed.status_code == 303
    assert SIGNING_SECRET not in closed.headers.values()
    detail = client.get(closed.headers["location"])
    assert detail.text.count("Coordinación interna planificada. Solicitud pendiente de registro.") == 1
    assert "closed" in detail.text
    assert 'name="outcome"' not in detail.text
    assert MSG_CONTEXT_UNAVAILABLE not in detail.text
    assert "El contexto clínico actual no se muestra cuando el caso está cerrado." in detail.text
    queue = client.get("/review-cases")
    assert case.case_id not in queue.text
    assert repository.events(case.id)[-1].event_type.value == "closed"


def test_same_outcome_close_does_not_append_another_event(tmp_path):
    repository = _repository(tmp_path)
    case = _create(repository)
    client = _client(repository, ScriptedFhir())
    page = client.get(f"/review-cases/{case.id}")
    _post_close(client, case.id, page.text, "review_completed_no_operational_action")
    stored = repository.get(case.id)
    issued = issue_form_token(
        secret=SIGNING_SECRET,
        review_case_id=case.id,
        expected_version=stored.version,
        session_id=_session_id(client),
        now=1_000,
    )
    assert issued is not None
    token, expiry = issued
    app.dependency_overrides[get_settings] = _settings
    from app import human_review_client

    original = human_review_client._now
    human_review_client._now = lambda: 1_000
    try:
        response = client.post(
            f"/review-cases/{case.id}/close",
            content=urlencode(
                {
                    "outcome": "review_completed_no_operational_action",
                    "expectedVersion": str(stored.version),
                    "formToken": token,
                    "formExpiry": str(expiry),
                }
            ),
            headers={**ORIGIN, "content-type": "application/x-www-form-urlencoded"},
            follow_redirects=False,
        )
    finally:
        human_review_client._now = original
    assert response.status_code == 303
    assert [event.event_type.value for event in repository.events(case.id)].count("closed") == 1


def test_conflict_then_closed_and_conflict_then_open(tmp_path):
    repository = _repository(tmp_path)
    case = _create(repository)
    fhir = ScriptedFhir()
    client = _client(repository, fhir)
    page = client.get(f"/review-cases/{case.id}")

    class ConflictRepository:
        def __init__(self, inner, mode: str) -> None:
            self.inner = inner
            self.mode = mode
            self.calls = 0

        def close(self, *args, **kwargs):
            self.calls += 1
            raise ReviewCaseConflict()

        def get_detail(self, review_case_id):
            detail = self.inner.get_detail(review_case_id)
            if self.mode != "open":
                return detail
            from dataclasses import replace

            return replace(detail, case=replace(detail.case, version=2))

        def __getattr__(self, name):
            return getattr(self.inner, name)

    closed_repo = ConflictRepository(repository, "closed")
    repository.close(case.id, expected_version=1, outcome=ReviewOutcome.FOLLOW_UP_COORDINATION_PLANNED)
    app.state.followup_review_repository = closed_repo
    conflict_closed = _post_close(client, case.id, page.text, "review_completed_no_operational_action")
    assert closed_repo.calls == 1
    assert conflict_closed.status_code == 303
    assert "notice" not in conflict_closed.headers["location"]
    closed_page = client.get(conflict_closed.headers["location"])
    assert "Coordinación interna planificada. Solicitud pendiente de registro." in closed_page.text

    repository = _repository(tmp_path, "open-review.sqlite3")
    case = _create(repository)
    client = _client(repository, fhir)
    page = client.get(f"/review-cases/{case.id}")
    open_repo = ConflictRepository(repository, "open")
    app.state.followup_review_repository = open_repo
    conflict_open = _post_close(client, case.id, page.text, "follow_up_coordination_planned")
    assert open_repo.calls == 1
    assert conflict_open.headers["location"].endswith("?notice=changed")
    refreshed = client.get(conflict_open.headers["location"])
    assert MSG_CHANGED in refreshed.text
    assert repository.get(case.id).status is ReviewCaseStatus.OPEN
    assert 'name="expectedVersion" value="2"' in refreshed.text
    refreshed_fields = _fields(refreshed.text)
    assert refreshed_fields["expectedVersion"] == "2"
    assert form_token_is_valid(
        secret=SIGNING_SECRET,
        review_case_id=case.id,
        expected_version=2,
        expiry=int(refreshed_fields["formExpiry"]),
        token=refreshed_fields["formToken"],
        session_id=_session_id(client),
    )
    assert not form_token_is_valid(
        secret=SIGNING_SECRET,
        review_case_id=case.id,
        expected_version=1,
        expiry=int(refreshed_fields["formExpiry"]),
        token=refreshed_fields["formToken"],
        session_id=_session_id(client),
    )

    class Guard:
        def __init__(self, inner) -> None:
            self.inner = inner
            self.calls = 0

        def close(self, *args, **kwargs):
            self.calls += 1
            raise AssertionError("close was invoked")

        def __getattr__(self, name):
            return getattr(self.inner, name)

    guard = Guard(repository)
    app.state.followup_review_repository = guard
    stale = _post_close(
        client,
        case.id,
        page.text,
        "follow_up_coordination_planned",
        expectedVersion="2",
    )
    assert stale.status_code == 400
    assert MSG_FORM_INVALID in stale.text
    assert guard.calls == 0


@pytest.mark.parametrize(
    ("overrides", "headers", "message"),
    [
        ({"outcome": "diagnosis"}, ORIGIN, MSG_CLOSE_INVALID),
        ({"expectedVersion": "0"}, ORIGIN, MSG_CLOSE_INVALID),
        ({"formToken": ""}, ORIGIN, MSG_FORM_INVALID),
        ({"formToken": "0" * 64}, ORIGIN, MSG_FORM_INVALID),
        ({"formExpiry": "1"}, ORIGIN, MSG_FORM_INVALID),
        ({}, {"origin": "http://evil.test"}, MSG_ORIGIN_INVALID),
        ({}, {}, MSG_ORIGIN_INVALID),
    ],
)
def test_invalid_close_does_not_call_the_service(tmp_path, overrides, headers, message):
    repository = _repository(tmp_path)
    case = _create(repository)

    class Guard:
        def __init__(self, inner) -> None:
            self.inner = inner
            self.calls = 0

        def close(self, *args, **kwargs):
            self.calls += 1
            raise AssertionError("close was invoked")

        def __getattr__(self, name):
            return getattr(self.inner, name)

    guard = Guard(repository)
    client = _client(guard, ScriptedFhir())
    page = client.get(f"/review-cases/{case.id}")
    response = client.post(
        f"/review-cases/{case.id}/close",
        content=urlencode({**_fields(page.text), "outcome": "follow_up_coordination_planned", **overrides}),
        headers={**headers, "content-type": "application/x-www-form-urlencoded"},
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert message in response.text
    assert guard.calls == 0
    assert SIGNING_SECRET not in response.text


def test_wrong_case_and_wrong_version_tokens_do_not_close(tmp_path):
    repository = _repository(tmp_path)
    case = _create(repository)
    other = _create(repository, case_id="SYN-FOLLOWUP-009", suffix="009")
    client = _client(repository, ScriptedFhir())
    page = client.get(f"/review-cases/{case.id}")
    fields = _fields(page.text)
    session_id = _session_id(client)
    other_token = issue_form_token(
        secret=SIGNING_SECRET,
        review_case_id=other.id,
        expected_version=1,
        session_id=session_id,
        now=int(fields["formExpiry"]) - FORM_TTL_SECONDS,
    )
    version_token = issue_form_token(
        secret=SIGNING_SECRET,
        review_case_id=case.id,
        expected_version=9,
        session_id=session_id,
        now=int(fields["formExpiry"]) - FORM_TTL_SECONDS,
    )
    assert other_token is not None and version_token is not None
    for token in (other_token[0], version_token[0]):
        response = client.post(
            f"/review-cases/{case.id}/close",
            content=urlencode(
                {
                    "outcome": "follow_up_coordination_planned",
                    "expectedVersion": "1",
                    "formToken": token,
                    "formExpiry": fields["formExpiry"],
                }
            ),
            headers={**ORIGIN, "content-type": "application/x-www-form-urlencoded"},
            follow_redirects=False,
        )
        assert response.status_code == 400
        assert MSG_FORM_INVALID in response.text
    assert repository.get(case.id).status is ReviewCaseStatus.OPEN


def test_signing_secret_is_separate_from_the_service_token(tmp_path):
    repository = _repository(tmp_path)
    case = _create(repository)
    client = _client(repository, ScriptedFhir())
    response = client.get(f"/review-cases/{case.id}")
    fields = _fields(response.text)
    session_id = _session_id(client)
    assert form_token_is_valid(
        secret=SIGNING_SECRET,
        review_case_id=case.id,
        expected_version=int(fields["expectedVersion"]),
        expiry=int(fields["formExpiry"]),
        token=fields["formToken"],
        session_id=session_id,
    )
    assert not form_token_is_valid(
        secret=SERVICE_TOKEN,
        review_case_id=case.id,
        expected_version=int(fields["expectedVersion"]),
        expiry=int(fields["formExpiry"]),
        token=fields["formToken"],
        session_id=session_id,
    )
    assert SIGNING_SECRET not in response.text
    assert SERVICE_TOKEN not in response.text
    assert SIGNING_SECRET not in response.headers.values()
    css = _client(repository).get("/review-static/review.css")
    assert SIGNING_SECRET not in css.text
    assert SERVICE_TOKEN not in css.text


def test_blank_signing_secret_does_not_fall_back_to_the_service_token(tmp_path, monkeypatch):
    repository = _repository(tmp_path)
    case = _create(repository)

    def settings() -> Settings:
        configured = _settings()
        return Settings(
            model_boundary_base_url=configured.model_boundary_base_url,
            model_boundary_path=configured.model_boundary_path,
            model_boundary_timeout_seconds=configured.model_boundary_timeout_seconds,
            model_boundary_service_token=SERVICE_TOKEN,
            host=configured.host,
            port=configured.port,
            followup_agent_enabled=True,
            ai_review_db_path=configured.ai_review_db_path,
            human_review_form_signing_secret="",
            human_session_db_path=configured.human_session_db_path,
            human_review_development_auth_enabled=True,
            human_review_development_auth_secret=configured.human_review_development_auth_secret,
            human_review_development_principal_id=configured.human_review_development_principal_id,
            human_review_development_principal_display_name=configured.human_review_development_principal_display_name,
        )

    app.state.followup_review_repository = repository
    app.state.clinical_context_fhir_client = lambda: ScriptedFhir()
    _prepare_session(repository)
    app.dependency_overrides[get_settings] = settings
    client = TestClient(app, base_url="http://127.0.0.1")
    _login(client)
    page = client.get(f"/review-cases/{case.id}")
    assert MSG_NOT_CONFIGURED in page.text
    assert 'name="formToken"' not in page.text
    issued = issue_form_token(
        secret=SERVICE_TOKEN,
        review_case_id=case.id,
        expected_version=1,
        session_id=TOKEN_SESSION,
        now=1_000,
    )
    assert issued is not None
    monkeypatch.setattr("app.human_review_client._now", lambda: 1_000)
    response = client.post(
        f"/review-cases/{case.id}/close",
        content=urlencode(
            {
                "outcome": "follow_up_coordination_planned",
                "expectedVersion": "1",
                "formToken": issued[0],
                "formExpiry": str(issued[1]),
            }
        ),
        headers={**ORIGIN, "content-type": "application/x-www-form-urlencoded"},
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert MSG_NOT_CONFIGURED in response.text
    assert repository.get(case.id).status is ReviewCaseStatus.OPEN
    assert SERVICE_TOKEN not in response.text


def test_malformed_form_does_not_invoke_close(tmp_path):
    repository = _repository(tmp_path)
    case = _create(repository)

    class Guard:
        def __init__(self, inner) -> None:
            self.inner = inner
            self.calls = 0

        def close(self, *args, **kwargs):
            self.calls += 1
            raise AssertionError("close was invoked")

        def __getattr__(self, name):
            return getattr(self.inner, name)

    guard = Guard(repository)
    client = _client(guard, ScriptedFhir())
    page = client.get(f"/review-cases/{case.id}")
    fields = _fields(page.text)
    non_ascii = client.post(
        f"/review-cases/{case.id}/close",
        content=urlencode(
            {
                "outcome": "follow_up_coordination_planned",
                "expectedVersion": fields["expectedVersion"],
                "formToken": "tóken",
                "formExpiry": fields["formExpiry"],
            }
        ),
        headers={**ORIGIN, "content-type": "application/x-www-form-urlencoded"},
        follow_redirects=False,
    )
    extra = "&".join(f"extra{index}=1" for index in range(9))
    too_many = client.post(
        f"/review-cases/{case.id}/close",
        content=urlencode(
            {
                "outcome": "follow_up_coordination_planned",
                "expectedVersion": fields["expectedVersion"],
                "formToken": fields["formToken"],
                "formExpiry": fields["formExpiry"],
            }
        )
        + "&"
        + extra,
        headers={**ORIGIN, "content-type": "application/x-www-form-urlencoded"},
        follow_redirects=False,
    )
    assert non_ascii.status_code == 400
    assert MSG_FORM_INVALID in non_ascii.text
    assert too_many.status_code == 400
    assert MSG_CLOSE_INVALID in too_many.text
    assert "ValueError" not in non_ascii.text
    assert "TypeError" not in non_ascii.text
    assert "ValueError" not in too_many.text
    assert guard.calls == 0
    assert SIGNING_SECRET not in non_ascii.text
    assert SIGNING_SECRET not in too_many.text


def test_expired_form_is_rejected_by_the_close_route(tmp_path, monkeypatch):
    repository = _repository(tmp_path)
    case = _create(repository)

    class Guard:
        def __init__(self, inner) -> None:
            self.inner = inner
            self.calls = 0

        def close(self, *args, **kwargs):
            self.calls += 1
            raise AssertionError("close was invoked")

        def __getattr__(self, name):
            return getattr(self.inner, name)

    guard = Guard(repository)
    monkeypatch.setattr("app.human_review_client._now", lambda: 1_000)
    client = _client(guard, ScriptedFhir())
    page = client.get(f"/review-cases/{case.id}")
    fields = _fields(page.text)
    monkeypatch.setattr("app.human_review_client._now", lambda: int(fields["formExpiry"]))
    response = _post_close(client, case.id, page.text, "follow_up_coordination_planned")
    assert response.status_code == 400
    assert MSG_FORM_INVALID in response.text
    assert "Traceback" not in response.text
    assert guard.calls == 0


def test_nested_projected_strings_are_escaped(tmp_path):
    repository = _repository(tmp_path)
    case = _create(repository)
    fhir = ScriptedFhir()
    payload = '"><img src=x onerror=alert(1)>'
    fhir.observation.pop("valueString")
    fhir.observation["code"] = {"coding": [{"display": payload, "code": "1"}]}
    fhir.observation["valueQuantity"] = {"value": 1, "unit": payload}
    fhir.appointments = [_appointment(payload, "2099-01-01T00:00:00Z")]
    response = _client(repository, fhir).get(f"/review-cases/{case.id}")
    assert response.status_code == 200
    assert payload not in response.text
    assert "<img" not in response.text
    assert response.text.count("&lt;img src=x onerror=alert(1)&gt;") >= 3


def test_expired_token_is_rejected():
    issued = issue_form_token(
        secret=SIGNING_SECRET,
        review_case_id="00000000-0000-4000-8000-000000000000",
        expected_version=1,
        session_id=TOKEN_SESSION,
        now=1_000,
    )
    assert issued is not None
    token, expiry = issued
    assert form_token_is_valid(
        secret=SIGNING_SECRET,
        review_case_id="00000000-0000-4000-8000-000000000000",
        expected_version=1,
        expiry=expiry,
        token=token,
        session_id=TOKEN_SESSION,
        now=1_000,
    )
    assert not form_token_is_valid(
        secret=SIGNING_SECRET,
        review_case_id="00000000-0000-4000-8000-000000000000",
        expected_version=1,
        expiry=expiry,
        token=token,
        session_id=TOKEN_SESSION,
        now=expiry,
    )


def test_static_css_has_no_secret():
    css = Path(__file__).resolve().parents[1].joinpath("app", "static", "human_review", "review.css").read_text(encoding="utf-8")
    assert SIGNING_SECRET not in css
    assert "Patient" not in css
    response = _client(None).get("/review-static/review.css")
    assert response.status_code == 200
    assert SIGNING_SECRET not in response.text


def test_presentation_module_does_not_call_a_model():
    source = Path(__file__).resolve().parents[1].joinpath("app", "human_review_client.py").read_text(encoding="utf-8").lower()
    for token in ("gemini", "followup_workflow", "resourceType".lower()):
        assert token not in source


def test_direct_closed_case_has_history_without_a_form(tmp_path):
    repository = _repository(tmp_path)
    case = _create(repository)
    repository.close(case.id, expected_version=1, outcome=ReviewOutcome.REVIEW_COMPLETED_NO_OPERATIONAL_ACTION)
    fhir = ScriptedFhir()
    response = _client(repository, fhir).get(f"/review-cases/{case.id}")
    assert response.text.count("Revisión finalizada sin acción operativa registrada.") == 1
    assert "<th>Evento</th>" in response.text
    assert 'name="outcome"' not in response.text
    assert fhir.calls == []


def test_queue_and_case_page_cover_missed_follow_up_without_encounter(tmp_path):
    repository = _repository(tmp_path)
    first = _create(repository)
    missed_protocol = ProtocolReviewResult(
        id=MISSED_FOLLOW_UP_REVIEW_V1,
        evaluation_status=ProtocolEvaluationStatus.MATCHED,
        reason_codes=("missed_follow_up_without_confirmed_replacement",),
        matched_resources=("Appointment/noshow-008",),
        human_review_status="required",
        human_review_reason="deterministic_missed_follow_up_protocol_match",
        action_status="proposed",
        action_type="review_follow_up_case",
    )
    missed = FollowUpReviewCaseService(repository).ensure_for_protocol(CASE, missed_protocol)
    assert missed is not None
    payload = '"><img src=x onerror=alert(1)>'
    fhir = ScriptedFhir()
    fhir.appointments = [
        _appointment("noshow", "2026-01-01T00:00:00Z", "noshow-008"),
        _appointment("booked", "2099-01-01T00:00:00Z", "appointment-008"),
    ]
    fhir.appointments[0]["status"] = payload
    client = _client(repository, fhir)
    queue = client.get("/review-cases")
    assert queue.status_code == 200
    assert "Revisión de un seguimiento no realizado" in queue.text
    assert MISSED_FOLLOW_UP_REVIEW_V1 in queue.text
    assert POST_CONSULTATION_RESULT_REVIEW_V1 in queue.text
    assert SIGNING_SECRET not in queue.text
    assert SERVICE_TOKEN not in queue.text
    page = client.get(f"/review-cases/{missed.id}")
    assert page.status_code == 200
    assert "Revisión de un seguimiento no realizado" in page.text
    assert "La cita de seguimiento no se completó" in page.text
    assert "no había otra cita futura confirmada" in page.text
    assert "Appointment/noshow-008" in page.text.split("<details>", 1)[1]
    assert "not rescheduled" not in page.text
    assert "<h3>Encounter</h3>" not in page.text
    assert "<h3>Observation</h3>" not in page.text
    assert "Próxima y confirmada" in page.text
    assert "<img" not in page.text
    assert "&lt;img src=x onerror=alert(1)&gt;" in page.text
    assert PATIENT not in page.text
    assert SIGNING_SECRET not in page.text
    assert SERVICE_TOKEN not in page.text
    first_page = client.get(f"/review-cases/{first.id}")
    assert "<h3>Encounter</h3>" in first_page.text
    assert "<h3>Observation</h3>" in first_page.text
    assert "Cita que originó el caso" not in first_page.text
    closed = _post_close(client, missed.id, page.text, "follow_up_coordination_planned")
    assert closed.status_code == 303
    stored = repository.get(missed.id)
    assert stored is not None
    assert stored.status is ReviewCaseStatus.CLOSED
    assert stored.outcome is ReviewOutcome.FOLLOW_UP_COORDINATION_PLANNED


_PENDING = "Coordinación interna planificada. Solicitud pendiente de registro."
_RECORDED = "Solicitud interna de coordinación registrada."
_NO_ACTION = "Revisión finalizada sin acción operativa registrada."
_NO_EXTERNAL = "Esto no envía un mensaje, no escribe FHIR y no agenda una cita."
_RULE = "La regla operativa de revisión se cumplió. Esto no es un diagnóstico ni una recomendación clínica."


def test_readable_utc_keeps_the_instant_and_invalid_text():
    original = "2026-09-30T17:04:05.123456Z"
    assert _readable_utc(original) == "30 de septiembre de 2026, 17:04:05 UTC"
    assert "17:04:05" in _readable_utc(original)
    for unchanged in ("2026-09-30T17:04:05Z", "not-a-date", "2026-13-30T00:00:00.000000Z"):
        assert _readable_utc(unchanged) == unchanged


def test_slice1_queue_detail_and_coordination_sentences(tmp_path):
    repository = _repository(tmp_path)
    post = _create(repository)
    missed = FollowUpReviewCaseService(repository).ensure_for_protocol(
        "SYN-FOLLOWUP-009",
        ProtocolReviewResult(
            id=MISSED_FOLLOW_UP_REVIEW_V1,
            evaluation_status=ProtocolEvaluationStatus.MATCHED,
            reason_codes=("missed_follow_up_without_confirmed_replacement",),
            matched_resources=("Appointment/noshow-009",),
            human_review_status="required",
            human_review_reason="deterministic_missed_follow_up_protocol_match",
            action_status="proposed",
            action_type="review_follow_up_case",
        ),
    )
    assert missed is not None
    client = _client(repository, ScriptedFhir())
    queue = client.get("/review-cases")
    assert 'lang="es"' in queue.text
    assert "Revisión de un resultado posterior a la consulta" in queue.text
    assert POST_CONSULTATION_RESULT_REVIEW_V1 in queue.text
    assert "Revisión de un seguimiento no realizado" in queue.text
    assert MISSED_FOLLOW_UP_REVIEW_V1 in queue.text
    assert _readable_utc(post.created_at) in queue.text
    assert post.created_at in queue.text
    assert "Demostración sintética de laboratorio" in queue.text
    assert "no es una identidad clínica verificada" in queue.text

    page = client.get(f"/review-cases/{post.id}")
    visible, technical = page.text.split("<details>", 1)
    assert technical.startswith("<summary>Detalles técnicos</summary>")
    assert "<details open" not in page.text
    assert _RULE in visible
    assert _RULE not in technical
    assert "matched" not in visible
    assert ">matched<" in technical
    assert "Encounter/encounter-008" not in visible
    assert "Encounter/encounter-008" in technical
    assert "Observation/observation-008" in technical
    assert "<h2>Historial operativo</h2>" in visible
    assert "<h2>Atribución de desarrollo</h2>" in visible
    assert "<h2>Historial operativo</h2>" not in technical
    assert "<h2>Atribución de desarrollo</h2>" not in technical
    assert "Los identificadores mostrados son principales sintéticos de desarrollo" in visible
    assert "Cierre del caso: aún no está cerrado." in visible
    assert "AI-assisted review" in visible
    assert page.text.count(_PENDING) == 1
    assert page.text.count(_NO_ACTION) == 1
    assert 'name="outcome" value="follow_up_coordination_planned"' in page.text
    assert 'name="outcome" value="review_completed_no_operational_action"' in page.text
    assert _readable_utc(post.created_at) in visible
    assert post.created_at not in visible
    assert post.created_at in technical
    session_id = _session_id(client)
    cookie = client.cookies.get(SESSION_COOKIE)
    assert cookie is not None
    for secret in (SIGNING_SECRET, SERVICE_TOKEN, DEV_SECRET, cookie, session_id):
        assert secret not in page.text
    login = client.get("/review-login")
    assert "Sign in" in login.text
    assert 'lang="en"' in login.text

    repository.close(
        post.id,
        expected_version=1,
        outcome=ReviewOutcome.FOLLOW_UP_COORDINATION_PLANNED,
    )
    planned = client.get(f"/review-cases/{post.id}")
    assert planned.text.count(_PENDING) == 1
    assert _RECORDED not in planned.text
    assert "Cierre del caso: no se registró atribución de desarrollo." in planned.text
    assert 'name="outcome"' not in planned.text

    FollowUpCoordinationActionService(repository).ensure_follow_up_coordination_request(post.id)
    requested = client.get(f"/review-cases/{post.id}")
    assert requested.text.count(_RECORDED) == 1
    assert "Solicitud pendiente de registro." not in requested.text
    assert _NO_EXTERNAL in requested.text
    assert "No se registró atribución de desarrollo para esta operación." in requested.text
    stored = repository.get_follow_up_coordination_request(post.id)
    assert stored is not None
    requested_visible, requested_technical = requested.text.split("<details>", 1)
    assert stored.id not in requested_visible
    assert stored.id in requested_technical
    assert ">requested<" in requested_technical

    no_action_case = _create(repository, case_id="SYN-FOLLOWUP-010", suffix="010")
    repository.close(
        no_action_case.id,
        expected_version=1,
        outcome=ReviewOutcome.REVIEW_COMPLETED_NO_OPERATIONAL_ACTION,
    )
    no_action = client.get(f"/review-cases/{no_action_case.id}")
    assert no_action.text.count(_NO_ACTION) == 1
    assert _PENDING not in no_action.text
    assert "Registrar solicitud de coordinación interna" not in no_action.text


def _missed_case(repository, case_id: str, appointment_id: str):
    case = FollowUpReviewCaseService(repository).ensure_for_protocol(
        case_id,
        ProtocolReviewResult(
            id=MISSED_FOLLOW_UP_REVIEW_V1,
            evaluation_status=ProtocolEvaluationStatus.MATCHED,
            reason_codes=("missed_follow_up_without_confirmed_replacement",),
            matched_resources=(f"Appointment/{appointment_id}",),
            human_review_status="required",
            human_review_reason="deterministic_missed_follow_up_protocol_match",
            action_status="proposed",
            action_type="review_follow_up_case",
        ),
    )
    assert case is not None
    return case


def test_slice2_origin_appointment_is_shown_once_and_other_stays_technical(tmp_path):
    repository = _repository(tmp_path)
    post = _create(repository)
    missed = _missed_case(repository, "SYN-FOLLOWUP-013", "noshow-013")
    separate = _missed_case(repository, "SYN-FOLLOWUP-014", "noshow-014")
    fhir = ScriptedFhir()
    fhir.appointments = [
        _appointment("noshow", "2026-01-01T00:00:00Z", "noshow-013"),
        _appointment("booked", "2099-01-01T00:00:00Z", "appointment-013"),
    ]
    fhir.exact_appointments = [_appointment("noshow", "2026-02-01T00:00:00Z", "noshow-014")]
    client = _client(repository, fhir)

    page = client.get(f"/review-cases/{missed.id}")
    visible, technical = page.text.split("<details>", 1)
    origin, appointments = visible.split("<h3>Appointments</h3>", 1)
    assert origin.count("<h3>Cita que originó el caso</h3>") == 1
    assert origin.count("Appointment/noshow-013") == 1
    assert "Appointment/noshow-013" not in appointments
    assert "La cita que originó este caso está arriba." in appointments
    assert appointments.count("Estado operativo de la cita no clasificado") == 1
    assert "Próxima y confirmada" in appointments
    assert "Other appointment status" not in page.text
    assert "Recorded appointment" not in page.text
    lowered = visible.lower()
    for banned in ("clinically", "clínicamente", "reschedul", "reprogram"):
        assert banned not in lowered
    assert ">OTHER<" in technical
    assert ">noshow<" in technical
    assert ">OTHER<" not in visible
    assert "<h3>Encounter</h3>" not in page.text
    assert "<h3>Observation</h3>" not in page.text

    post_page = client.get(f"/review-cases/{post.id}")
    assert "<h3>Encounter</h3>" in post_page.text
    assert "<h3>Observation</h3>" in post_page.text
    assert "Cita que originó el caso" not in post_page.text
    assert "La cita que originó este caso está arriba." not in post_page.text

    alone = client.get(f"/review-cases/{separate.id}")
    alone_visible = alone.text.split("<details>", 1)[0]
    alone_origin, alone_list = alone_visible.split("<h3>Appointments</h3>", 1)
    assert alone_origin.count("Appointment/noshow-014") == 1
    assert "Appointment/noshow-014" not in alone_list
    assert "La cita que originó este caso está arriba." not in alone.text
    assert "<h3>Cita que originó el caso</h3>" in alone_origin
