"""LangGraph orchestration. Gemini is simulated. Historical reviews are not used."""

from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.followup_review import (
    FollowUpReviewCaseService,
    ProtocolEvaluationStatus,
    ReviewCaseStatus,
    ReviewOutcome,
)
from app.followup_review_sqlite import SQLiteFollowUpReviewCaseRepository
from app.human_review_client import _workflow_section
from app.langgraph_workflow_orchestration import (
    GRAPH_NODES,
    MISSED_FOLLOW_UP,
    POST_CONSULTATION,
    SqliteCheckpointSaver,
    WorkflowDecisionRejected,
    WorkflowNotSuspended,
    WorkflowReadError,
    compile_workflow,
    execution_snapshot,
    read_workflow_record,
    resume_after_human_decision,
    resume_workflow,
    start_workflow,
    workflow_id_for,
)
from app.main import app, get_settings
from app.missed_follow_up_review import (
    REASON_MISSED,
    REASON_NO_NOSHOW,
    MissedFollowUpAppointment,
    MissedFollowUpSnapshot,
    evaluate_missed_follow_up,
)
from app.post_consultation_review import (
    POST_CONSULTATION_RESULT_REVIEW_V1,
    AppointmentFact,
    CollectionState,
    PostConsultationSnapshot,
    ProtocolReviewResult,
    evaluate_post_consultation_review,
)
from app.followup_service import resume_after_human_decision as resume_from_service


TOKEN = "test-model-boundary-token"
AUTH = {"X-Service-Token": TOKEN}
INSTANT = datetime(2026, 10, 21, tzinfo=timezone.utc)
PATIENT = "MHS-PAT-015"
MATCHED_CASE = "SYN-FOLLOWUP-016"
MISSED_CASE = "SYN-FOLLOWUP-017"
NOT_MATCHED_CASE = "SYN-FOLLOWUP-018"
INSUFFICIENT_CASE = "SYN-FOLLOWUP-019"
UNAVAILABLE_CASE = "SYN-FOLLOWUP-020"
GEMINI_CASE = "SYN-FOLLOWUP-021"
DUPLICATE_CASE = "SYN-FOLLOWUP-022"
RESUME_CASE = "SYN-FOLLOWUP-023"
LONGITUDINAL_CASE = "SYN-FOLLOWUP-024"
NARRATIVE = "Propuesta operativa sintética para revisión humana."


class Clock:
    def __init__(self) -> None:
        self.value = INSTANT

    def __call__(self):
        current = self.value
        self.value += timedelta(seconds=1)
        return current


class ScriptedPorts:
    def __init__(self, evaluation, *, narrative: str = "prepared", fail_read: bool = False) -> None:
        self.evaluation = evaluation
        self.narrative = narrative
        self.fail_read = fail_read
        self.fail_after_ensure = False
        self.ensure_calls = 0
        self.provider_calls = 0
        self.evaluate_calls = 0
        self.reviews: dict[str, str] = {}
        self.pending: dict[str, str] = {}
        self.narratives: dict[str, str] = {}
        self.narrative_by_case: dict[str, str] = {}
        self.external_ensure = None

    def read_patient(self, case_id: str, workflow_type: str) -> str:
        del case_id, workflow_type
        if self.fail_read:
            raise WorkflowReadError("acquisition_unavailable")
        return f"Patient/{PATIENT}"

    def build_context(self, case_id: str) -> dict:
        del case_id
        return {
            "context": {
                "schema": "LONGITUDINAL_CONTEXT_V1",
                "contextStatus": "complete",
                "truncated": False,
                "counts": {"encounters": 1, "observations": 1, "appointments": 1},
            },
            "intelligence": {
                "schema": "CLINICAL_CONTEXT_INTELLIGENCE_V1",
                "contextStatus": "complete",
                "truncated": False,
                "relationCodes": ["observation_encounter"],
                "missing": [],
                "conflictCodes": [],
            },
        }

    def evaluate(self, case_id: str, workflow_type: str) -> dict:
        self.evaluate_calls += 1
        if self.fail_read:
            raise AssertionError("a failed read must not evaluate the protocol")
        if callable(self.evaluation):
            return self.evaluation(case_id, workflow_type)
        return self.evaluation

    def prepare_narrative(self, state: dict) -> str:
        if state["case_id"] in self.narrative_by_case:
            return "stored"
        self.provider_calls += 1
        if self.narrative == "unavailable":
            return "unavailable"
        self.pending[state["workflow_id"]] = NARRATIVE
        return "prepared"

    def ensure_review(self, state: dict) -> str:
        self.ensure_calls += 1
        if self.external_ensure is not None:
            review_id = self.external_ensure(state)
        else:
            review_id = self.reviews.get(state["workflow_id"]) or f"review-{state['case_id']}"
        self.reviews[state["workflow_id"]] = review_id
        return review_id

    def store_prepared_narrative(self, review_case_id: str, state: dict) -> None:
        text = self.pending.pop(state["workflow_id"], None)
        if not review_case_id or not text or review_case_id in self.narratives:
            return
        self.narratives[review_case_id] = text
        self.narrative_by_case.setdefault(state["case_id"], text)


def _settings(**overrides) -> Settings:
    values = {
        "model_boundary_base_url": "http://model-boundary.test",
        "model_boundary_path": "/api/model-boundary/v1",
        "model_boundary_timeout_seconds": 5,
        "model_boundary_service_token": TOKEN,
        "host": "127.0.0.1",
        "port": 8090,
        "followup_agent_enabled": True,
        "ai_review_db_path": "unused-review.sqlite3",
    }
    values.update(overrides)
    return Settings(**values)


def _saver(tmp_path) -> SqliteCheckpointSaver:
    return SqliteCheckpointSaver(tmp_path / "agent-workflow.sqlite3")


def _repository(tmp_path) -> SQLiteFollowUpReviewCaseRepository:
    repository = SQLiteFollowUpReviewCaseRepository(tmp_path / "review.sqlite3", clock=Clock())
    repository.initialize()
    return repository


def _protocol_view(result) -> dict:
    if hasattr(result, "evaluation_status"):
        protocol_id = result.id
        status = result.evaluation_status.value
        evidence = list(result.matched_resources)
    else:
        protocol_id = "MISSED_FOLLOW_UP_REVIEW_V1"
        status = result.status.value
        evidence = list(result.triggers or result.provenance_resources)
    return {
        "protocolId": protocol_id,
        "evaluationStatus": status,
        "reasonCodes": list(result.reason_codes),
        "evidence": evidence,
    }


def _post_snapshot(**overrides) -> PostConsultationSnapshot:
    encounter = {
        "resourceType": "Encounter",
        "id": "MHS-CON-024",
        "status": "finished",
        "subject": {"reference": f"Patient/{PATIENT}"},
        "period": {"end": "2024-06-01T10:00:00Z"},
    }
    observation = {
        "resourceType": "Observation",
        "id": "MHS-RES-026",
        "status": "final",
        "subject": {"reference": f"Patient/{PATIENT}"},
        "encounter": {"reference": "Encounter/MHS-CON-024"},
        "issued": "2024-06-01T12:00:00Z",
    }
    values = {
        "patient_id": PATIENT,
        "patient_state": CollectionState.COMPLETE,
        "encounter_state": CollectionState.COMPLETE,
        "observation_state": CollectionState.COMPLETE,
        "appointment_state": CollectionState.COMPLETE,
        "encounters": (encounter,),
        "observations": (observation,),
        "appointments": (),
    }
    values.update(overrides)
    return PostConsultationSnapshot(**values)


def _post_evaluation(**overrides):
    def evaluate(case_id: str, workflow_type: str) -> dict:
        del case_id, workflow_type
        return _protocol_view(evaluate_post_consultation_review(_post_snapshot(**overrides)))

    return evaluate


def _missed_evaluation(*appointments: MissedFollowUpAppointment):
    def evaluate(case_id: str, workflow_type: str) -> dict:
        del case_id, workflow_type
        snapshot = MissedFollowUpSnapshot(
            patient_id=PATIENT,
            patient_state=CollectionState.COMPLETE,
            appointment_state=CollectionState.COMPLETE,
            appointments=appointments,
            evaluated_at=INSTANT,
        )
        return _protocol_view(evaluate_missed_follow_up(snapshot))

    return evaluate


def _real_ensure(service: FollowUpReviewCaseService):
    def ensure(state: dict) -> str:
        missed = state["workflow_type"] == MISSED_FOLLOW_UP
        protocol = ProtocolReviewResult(
            id="MISSED_FOLLOW_UP_REVIEW_V1" if missed else POST_CONSULTATION_RESULT_REVIEW_V1,
            evaluation_status=ProtocolEvaluationStatus.MATCHED,
            reason_codes=(REASON_MISSED if missed else "post_consultation_result_requires_review",),
            matched_resources=(state["evidence"][0],),
            human_review_status="required",
            human_review_reason="deterministic_protocol_match",
            action_status="proposed",
            action_type="review_follow_up_case",
        )
        case = service.ensure_for_protocol(state["case_id"], protocol)
        assert case is not None
        return case.id

    return ensure


def _start(tmp_path, case_id: str, workflow_type: str, ports: ScriptedPorts) -> tuple[SqliteCheckpointSaver, dict]:
    saver = _saver(tmp_path)
    return saver, start_workflow(saver, ports, case_id, workflow_type)


@pytest.fixture(autouse=True)
def _clean_app_state():
    app.dependency_overrides.clear()
    for name in ("followup_review_repository", "agent_workflow_ports", "agent_workflow_saver"):
        if hasattr(app.state, name):
            delattr(app.state, name)
    yield
    app.dependency_overrides.clear()
    for name in ("followup_review_repository", "agent_workflow_ports", "agent_workflow_saver"):
        if hasattr(app.state, name):
            delattr(app.state, name)


def test_graph_has_the_orchestration_nodes(tmp_path):
    graph = compile_workflow(ScriptedPorts(_post_evaluation()), _saver(tmp_path))
    assert set(GRAPH_NODES) <= set(graph.get_graph().nodes)


def test_lg01_post_consultation_waits_for_human_review(tmp_path):
    ports = ScriptedPorts(_post_evaluation())
    saver, view = _start(tmp_path, MATCHED_CASE, POST_CONSULTATION, ports)
    assert view["status"] == "waiting_human"
    assert view["currentStep"] == "await_human"
    assert view["workflowId"] == workflow_id_for(MATCHED_CASE, POST_CONSULTATION)
    assert view["protocol"]["evaluationStatus"] == "matched"
    assert view["protocol"]["protocolId"] == POST_CONSULTATION_RESULT_REVIEW_V1
    assert view["reviewCaseId"] == f"review-{MATCHED_CASE}"
    assert view["narrativeStatus"] == "prepared"
    assert view["humanDecision"] is None
    assert ports.ensure_calls == 1
    assert ports.provider_calls == 1
    assert view["steps"] == [
        "clinical_read",
        "context_intelligence",
        "protocol_evaluation",
        "eligibility_router",
        "narrative",
        "human_review",
    ]
    blob = _checkpoint_blob(saver.path)
    assert NARRATIVE.encode("utf-8") not in blob
    assert b"g/dL" not in blob
    snapshot = execution_snapshot(saver, view["workflowId"])
    assert snapshot["interrupts"] == 1
    assert snapshot["view"]["status"] == "waiting_human"


def test_lg02_missed_follow_up_waits_for_human_review(tmp_path):
    ports = ScriptedPorts(
        _missed_evaluation(
            MissedFollowUpAppointment(
                "Appointment/MHS-APT-010",
                "MHS-APT-010",
                "noshow",
                datetime(2025, 9, 16, 12, tzinfo=timezone.utc),
            )
        )
    )
    _, view = _start(tmp_path, MISSED_CASE, MISSED_FOLLOW_UP, ports)
    assert view["status"] == "waiting_human"
    assert view["protocol"]["protocolId"] == "MISSED_FOLLOW_UP_REVIEW_V1"
    assert view["protocol"]["evaluationStatus"] == "matched"
    assert view["protocol"]["reasonCodes"] == [REASON_MISSED]
    assert view["evidence"] == ["Appointment/MHS-APT-010"]
    assert ports.ensure_calls == 1


def test_lg03_not_matched_finishes_without_review(tmp_path):
    ports = ScriptedPorts(_missed_evaluation(
        MissedFollowUpAppointment(
            "Appointment/MHS-APT-012",
            "MHS-APT-012",
            "cancelled",
            datetime(2026, 9, 21, 12, tzinfo=timezone.utc),
        )
    ))
    _, view = _start(tmp_path, NOT_MATCHED_CASE, MISSED_FOLLOW_UP, ports)
    assert view["status"] == "completed"
    assert view["protocol"]["evaluationStatus"] == "not_matched"
    assert view["protocol"]["reasonCodes"] == [REASON_NO_NOSHOW]
    assert view["reviewCaseId"] is None
    assert view["reviewStatus"] == "not_required"
    assert ports.ensure_calls == 0
    assert ports.provider_calls == 0


def test_lg04_insufficient_finishes_without_review(tmp_path):
    ports = ScriptedPorts(_post_evaluation(observations=()))
    _, view = _start(tmp_path, INSUFFICIENT_CASE, POST_CONSULTATION, ports)
    assert view["status"] == "completed"
    assert view["protocol"]["evaluationStatus"] == "insufficient"
    assert "final_observation_missing" in view["protocol"]["reasonCodes"]
    assert view["reviewCaseId"] is None
    assert ports.ensure_calls == 0
    assert ports.provider_calls == 0


def test_lg05_unavailable_java_is_recoverable(tmp_path):
    ports = ScriptedPorts(_post_evaluation(), fail_read=True)
    _, view = _start(tmp_path, UNAVAILABLE_CASE, POST_CONSULTATION, ports)
    assert view["status"] == "failed"
    assert view["errorCode"] == "acquisition_unavailable"
    assert view["protocol"]["evaluationStatus"] == "unavailable"
    assert ports.evaluate_calls == 0
    assert ports.ensure_calls == 0
    assert ports.provider_calls == 0


def test_lg06_gemini_failure_preserves_review(tmp_path):
    ports = ScriptedPorts(_post_evaluation(), narrative="unavailable")
    _, view = _start(tmp_path, GEMINI_CASE, POST_CONSULTATION, ports)
    assert view["status"] == "waiting_human"
    assert view["narrativeStatus"] == "unavailable"
    assert view["reviewCaseId"] == f"review-{GEMINI_CASE}"
    assert ports.narratives == {}
    assert ports.ensure_calls == 1
    assert ports.provider_calls == 1


def test_existing_narrative_is_not_replaced_or_regenerated(tmp_path):
    ports = ScriptedPorts(_post_evaluation())
    ports.narrative_by_case[DUPLICATE_CASE] = NARRATIVE
    _, view = _start(tmp_path, DUPLICATE_CASE, POST_CONSULTATION, ports)
    assert view["narrativeStatus"] == "stored"
    assert ports.provider_calls == 0
    assert ports.narratives == {}
    assert ports.narrative_by_case[DUPLICATE_CASE] == NARRATIVE


def test_lg07_duplicate_start_reuses_the_workflow(tmp_path):
    ports = ScriptedPorts(_post_evaluation())
    saver, first = _start(tmp_path, DUPLICATE_CASE, POST_CONSULTATION, ports)
    second = start_workflow(saver, ports, DUPLICATE_CASE, POST_CONSULTATION)
    assert second == first
    assert ports.ensure_calls == 1
    assert ports.provider_calls == 1
    assert ports.evaluate_calls == 1


def test_lg08_checkpoint_survives_a_new_saver(tmp_path):
    ports = ScriptedPorts(_post_evaluation())
    saver, view = _start(tmp_path, MATCHED_CASE, POST_CONSULTATION, ports)
    restored = SqliteCheckpointSaver(saver.path)
    snapshot = execution_snapshot(restored, view["workflowId"])
    assert snapshot["interrupts"] == 1
    assert snapshot["view"]["status"] == "waiting_human"
    assert snapshot["view"]["reviewCaseId"] == view["reviewCaseId"]
    assert read_workflow_record(saver.path, view["workflowId"])["status"] == "waiting_human"


def test_lg09_valid_decision_resumes_and_finishes(tmp_path):
    service = FollowUpReviewCaseService(_repository(tmp_path))
    ports = ScriptedPorts(_post_evaluation())
    ports.external_ensure = _real_ensure(service)
    saver, view = _start(tmp_path, RESUME_CASE, POST_CONSULTATION, ports)
    review_id = view["reviewCaseId"]
    outcome = ReviewOutcome.REVIEW_COMPLETED_NO_OPERATIONAL_ACTION
    closed = service.close(review_id, expected_version=1, outcome=outcome)
    resumed = resume_workflow(
        saver,
        ports,
        view["workflowId"],
        outcome.value,
        review_case_id=review_id,
        stored_outcome=closed.outcome.value,
        case_is_closed=True,
    )
    assert resumed["status"] == "completed"
    assert resumed["humanDecision"] == outcome.value
    assert resumed["reviewStatus"] == "closed"
    assert "await_human" in resumed["steps"]
    assert resumed["steps"][-1] == "completion"
    assert ports.ensure_calls == 1
    assert ports.provider_calls == 1
    assert service.get(review_id).version == 2
    assert len(service.events(review_id)) == 2


def test_lg10_repeated_resume_does_not_repeat_effects(tmp_path):
    service = FollowUpReviewCaseService(_repository(tmp_path))
    ports = ScriptedPorts(_post_evaluation())
    ports.external_ensure = _real_ensure(service)
    saver, view = _start(tmp_path, RESUME_CASE, POST_CONSULTATION, ports)
    outcome = ReviewOutcome.FOLLOW_UP_COORDINATION_PLANNED
    service.close(view["reviewCaseId"], expected_version=1, outcome=outcome)
    resume_workflow(
        saver,
        ports,
        view["workflowId"],
        outcome.value,
        review_case_id=view["reviewCaseId"],
        stored_outcome=outcome.value,
        case_is_closed=True,
    )
    with pytest.raises(WorkflowNotSuspended):
        resume_workflow(
            saver,
            ports,
            view["workflowId"],
            outcome.value,
            review_case_id=view["reviewCaseId"],
            stored_outcome=outcome.value,
            case_is_closed=True,
        )
    assert ports.ensure_calls == 1
    assert ports.provider_calls == 1
    assert service.get(view["reviewCaseId"]).version == 2


def test_lg11_unauthorized_resume_is_rejected(tmp_path):
    service = FollowUpReviewCaseService(_repository(tmp_path))
    ports = ScriptedPorts(_post_evaluation())
    ports.external_ensure = _real_ensure(service)
    saver, view = _start(tmp_path, RESUME_CASE, POST_CONSULTATION, ports)
    outcome = ReviewOutcome.REVIEW_COMPLETED_NO_OPERATIONAL_ACTION
    service.close(view["reviewCaseId"], expected_version=1, outcome=outcome)
    with pytest.raises(WorkflowDecisionRejected):
        resume_workflow(
            saver,
            ports,
            view["workflowId"],
            ReviewOutcome.FOLLOW_UP_COORDINATION_PLANNED.value,
            review_case_id=view["reviewCaseId"],
            stored_outcome=outcome.value,
            case_is_closed=True,
        )
    assert read_workflow_record(saver.path, view["workflowId"])["status"] == "waiting_human"
    assert ports.ensure_calls == 1
    assert service.get(view["reviewCaseId"]).version == 2


def test_lg12_longitudinal_not_matched_does_not_open_review(tmp_path):
    ports = ScriptedPorts(
        _post_evaluation(
            appointments=(AppointmentFact("Appointment/MHS-APT-021", "UPCOMING_CONFIRMED"),)
        )
    )
    _, view = _start(tmp_path, LONGITUDINAL_CASE, POST_CONSULTATION, ports)
    assert view["caseId"] == LONGITUDINAL_CASE
    assert view["status"] == "completed"
    assert view["protocol"]["evaluationStatus"] == "not_matched"
    assert view["protocol"]["reasonCodes"] == ["upcoming_confirmed_appointment"]
    assert "Appointment/MHS-APT-021" in view["evidence"]
    assert view["reviewCaseId"] is None
    assert ports.ensure_calls == 0
    assert ports.provider_calls == 0


def test_lg13_concurrent_starts_create_one_review(tmp_path):
    ports = ScriptedPorts(_post_evaluation())
    saver = _saver(tmp_path)

    def run(_: int) -> dict:
        return start_workflow(saver, ports, DUPLICATE_CASE, POST_CONSULTATION)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, (1, 2)))
    assert results[0]["workflowId"] == results[1]["workflowId"]
    assert results[0]["status"] == "waiting_human"
    assert results[1]["status"] == "waiting_human"
    assert ports.ensure_calls == 1
    assert ports.provider_calls == 1


def test_lg14_crash_after_review_does_not_duplicate_it(tmp_path):
    service = FollowUpReviewCaseService(_repository(tmp_path))
    ports = ScriptedPorts(_post_evaluation())
    ports.external_ensure = _real_ensure(service)
    ports.fail_after_ensure = True
    saver, failed = _start(tmp_path, MATCHED_CASE, POST_CONSULTATION, ports)
    assert failed["status"] == "failed"
    assert failed["errorCode"] == "node_failed"
    assert len(service.list_cases(status=ReviewCaseStatus.OPEN, case_id=MATCHED_CASE, limit=10, after=None).items) == 1
    ports.fail_after_ensure = False
    retried = start_workflow(saver, ports, MATCHED_CASE, POST_CONSULTATION)
    cases = service.list_cases(status=ReviewCaseStatus.OPEN, case_id=MATCHED_CASE, limit=10, after=None).items
    assert len(cases) == 1
    assert cases[0].version == 1
    assert retried["status"] == "waiting_human"
    assert retried["reviewCaseId"] == cases[0].id
    assert ports.provider_calls == 1
    assert ports.narratives[cases[0].id] == NARRATIVE


def test_lg15_resume_of_finished_workflow_is_rejected(tmp_path):
    ports = ScriptedPorts(_post_evaluation(observations=()))
    saver, view = _start(tmp_path, INSUFFICIENT_CASE, POST_CONSULTATION, ports)
    assert view["status"] == "completed"
    with pytest.raises(WorkflowNotSuspended):
        resume_workflow(
            saver,
            ports,
            view["workflowId"],
            ReviewOutcome.REVIEW_COMPLETED_NO_OPERATIONAL_ACTION.value,
            review_case_id="not-the-case",
            stored_outcome=ReviewOutcome.REVIEW_COMPLETED_NO_OPERATIONAL_ACTION.value,
            case_is_closed=True,
        )
    assert ports.ensure_calls == 0


def test_close_without_a_waiting_workflow_changes_nothing(tmp_path):
    settings = _settings(ai_review_db_path=str(tmp_path / "missing" / "review.sqlite3"))
    assert resume_from_service(settings, object(), "unused", ReviewOutcome.REVIEW_COMPLETED_NO_OPERATIONAL_ACTION.value) is None
    assert resume_after_human_decision(settings, object(), "unused", "review_completed_no_operational_action") is None


def test_review_page_reads_workflow_without_a_decision_control(tmp_path):
    service = FollowUpReviewCaseService(_repository(tmp_path))
    ports = ScriptedPorts(_post_evaluation())
    ports.external_ensure = _real_ensure(service)
    settings = _settings(ai_review_db_path=str(tmp_path / "review.sqlite3"))
    _, view = _start(tmp_path, RESUME_CASE, POST_CONSULTATION, ports)
    case = service.get(view["reviewCaseId"])
    html = _workflow_section(case, settings)
    assert view["workflowId"] in html
    assert "post_consultation" in html
    assert "waiting_human" in html
    assert "POST_CONSULTATION_RESULT_REVIEW_V1" in html
    assert "Referencia leída del HIS" in html
    assert "Evaluación determinista del protocolo" in html
    assert "Propuesta de IA" in html
    assert "Decisión humana del workflow" in html
    assert "Pendiente de decisión humana." in html
    assert "Esta vista no reanuda el workflow ni registra una decisión." in html
    assert "<form" not in html
    assert "No hay un workflow" in _workflow_section(case, _settings(ai_review_db_path=str(tmp_path / "other" / "review.sqlite3")))


def test_internal_workflow_api_auth_read_and_resume(tmp_path):
    repository = _repository(tmp_path)
    service = FollowUpReviewCaseService(repository)
    ports = ScriptedPorts(_post_evaluation())
    ports.external_ensure = _real_ensure(service)
    saver = _saver(tmp_path)
    app.state.followup_review_repository = repository
    app.state.agent_workflow_ports = ports
    app.state.agent_workflow_saver = saver
    app.dependency_overrides[get_settings] = lambda: _settings(ai_review_db_path=str(tmp_path / "review.sqlite3"))
    client = TestClient(app)
    denied = client.post("/internal/workflows", json={"caseId": MATCHED_CASE, "workflowType": POST_CONSULTATION})
    assert denied.status_code == 401
    invalid = client.post(
        "/internal/workflows",
        headers=AUTH,
        json={"caseId": "SYN-FOLLOWUP-999", "workflowType": POST_CONSULTATION},
    )
    assert invalid.status_code == 422
    started = client.post(
        "/internal/workflows",
        headers=AUTH,
        json={"caseId": MATCHED_CASE, "workflowType": POST_CONSULTATION},
    )
    assert started.status_code == 200
    body = started.json()
    workflow_id = body["workflowId"]
    assert body["status"] == "waiting_human"
    again = client.get(f"/internal/workflows/{workflow_id}", headers=AUTH)
    assert again.status_code == 200
    assert again.json() == body
    assert ports.ensure_calls == 1
    steps = client.get(f"/internal/workflows/{workflow_id}/steps", headers=AUTH)
    assert steps.json()["steps"][0] == "clinical_read"
    evidence = client.get(f"/internal/workflows/{workflow_id}/evidence", headers=AUTH)
    assert NARRATIVE not in evidence.text
    assert evidence.json()["protocol"]["evaluationStatus"] == "matched"
    errors = client.get(f"/internal/workflows/{workflow_id}/errors", headers=AUTH)
    assert errors.json()["errorCode"] is None
    early = client.post(
        f"/internal/workflows/{workflow_id}/resume",
        headers=AUTH,
        json={"reviewCaseId": body["reviewCaseId"], "decision": ReviewOutcome.REVIEW_COMPLETED_NO_OPERATIONAL_ACTION.value},
    )
    assert early.status_code == 403
    assert ports.ensure_calls == 1
    outcome = ReviewOutcome.REVIEW_COMPLETED_NO_OPERATIONAL_ACTION
    service.close(body["reviewCaseId"], expected_version=1, outcome=outcome)
    rejected = client.post(
        f"/internal/workflows/{workflow_id}/resume",
        headers=AUTH,
        json={"reviewCaseId": body["reviewCaseId"], "decision": ReviewOutcome.FOLLOW_UP_COORDINATION_PLANNED.value},
    )
    assert rejected.status_code == 403
    assert client.get(f"/internal/workflows/{workflow_id}", headers=AUTH).json()["status"] == "waiting_human"
    resumed = client.post(
        f"/internal/workflows/{workflow_id}/resume",
        headers=AUTH,
        json={"reviewCaseId": body["reviewCaseId"], "decision": outcome.value},
    )
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "completed"
    assert resumed.json()["humanDecision"] == outcome.value
    repeated = client.post(
        f"/internal/workflows/{workflow_id}/resume",
        headers=AUTH,
        json={"reviewCaseId": body["reviewCaseId"], "decision": outcome.value},
    )
    assert repeated.status_code == 409
    assert service.get(body["reviewCaseId"]).version == 2
    assert ports.provider_calls == 1


def _checkpoint_blob(path) -> bytes:
    connection = sqlite3.connect(path)
    try:
        row = connection.execute("SELECT payload FROM checkpoint_state WHERE id = 1").fetchone()
    finally:
        connection.close()
    assert row is not None
    return row[0]
