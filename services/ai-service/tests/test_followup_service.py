from __future__ import annotations

import logging
import uuid

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from app.config import Settings
from app.langgraph_fhir_client import POLICY_VERSION, InMemoryAuditSink, PreparedReadClient
from app.langgraph_followup_workflow import FollowUpWorkflow, FollowUpWorkflowResult
from app.langgraph_gemini_fhir_followup import followup_message_from_response
from app.main import app, get_settings


CASE = "SYN-FOLLOWUP-001"
FORBIDDEN_BODY_KEYS = {
    "agent",
    "agentVersion",
    "promptVersion",
    "suggestedActions",
    "requiresHumanReview",
    "summary",
    "reason",
    "modelCalled",
}


def _settings(**overrides) -> Settings:
    values = {
        "model_boundary_base_url": "http://model-boundary.test",
        "model_boundary_path": "/api/model-boundary/v1",
        "model_boundary_timeout_seconds": 5,
        "model_boundary_service_token": "test-model-boundary-token",
        "host": "127.0.0.1",
        "port": 8090,
        "llm_experimental_enabled": False,
        "gemini_api_key": "",
        "gemini_model": "gemini-flash-latest",
        "followup_agent_enabled": True,
    }
    values.update(overrides)
    return Settings(**values)


def _auth_headers() -> dict[str, str]:
    return {
        "X-Service-Token": "test-model-boundary-token",
        "X-Correlation-ID": "corr-followup",
    }


def _post(client: TestClient, payload, headers=None):
    return client.post("/internal/agent/follow-up", json=payload, headers=headers)


class _ScriptedWorkflow:
    def __init__(self, run_id: str, result: FollowUpWorkflowResult) -> None:
        self.run_id = run_id
        self.result = result
        self.cases: list[str] = []

    def run(self, case_id: str) -> FollowUpWorkflowResult:
        self.cases.append(case_id)
        return FollowUpWorkflowResult(
            case_id=case_id,
            status=self.result.status,
            final_answer=self.result.final_answer,
            patient=self.result.patient,
            observations=list(self.result.observations),
            evidence=[dict(item) for item in self.result.evidence],
            tools_used=list(self.result.tools_used),
            turns=self.result.turns,
            run_id=self.run_id,
            follow_up_required=self.result.follow_up_required,
        )


def _result(status: str, answer: str, **overrides) -> FollowUpWorkflowResult:
    values = {
        "case_id": CASE,
        "status": status,
        "final_answer": answer,
        "patient": {"resourceType": "Patient", "id": "SYN-PATIENT-001"},
        "observations": [{"resourceType": "Observation", "id": "obs-synthetic-001", "valueString": "12"}],
        "evidence": [
            {
                "tool": "get_patient_followup_context",
                "resources": ["Patient/SYN-PATIENT-001", "Observation/obs-synthetic-001"],
            }
        ],
        "tools_used": ["get_patient_followup_context"],
        "turns": 2,
        "run_id": "ignored-by-the-script",
        "follow_up_required": "unknown",
    }
    values.update(overrides)
    return FollowUpWorkflowResult(**values)


def _client(monkeypatch, settings: Settings, result: FollowUpWorkflowResult | None = None, *, fail: bool = False):
    seen: dict[str, object] = {"runs": []}

    def factory(run_id: str):
        if fail:
            raise AssertionError("workflow must not run")
        workflow = _ScriptedWorkflow(run_id, result or _result("finish", "Synthetic answer."))
        seen["runs"].append(workflow)
        return workflow

    monkeypatch.setattr("app.followup_service.build_followup_workflow", factory)
    app.dependency_overrides[get_settings] = lambda: settings
    seen["factory"] = factory
    return TestClient(app), seen


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


def test_health_stays_unauthenticated():
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_missing_service_token_is_401_and_does_not_run_the_workflow(monkeypatch):
    client, seen = _client(monkeypatch, _settings(), fail=True)
    response = _post(client, {"caseId": CASE}, headers={})
    assert response.status_code == 401
    assert response.content == b""
    assert seen["runs"] == []
    assert "test-model-boundary-token" not in response.text


def test_invalid_service_token_is_401_and_does_not_run_the_workflow(monkeypatch):
    client, seen = _client(monkeypatch, _settings(), fail=True)
    response = _post(client, {"caseId": CASE}, headers={"X-Service-Token": "wrong"})
    assert response.status_code == 401
    assert response.content == b""
    assert seen["runs"] == []


def test_blank_configured_token_is_fail_closed(monkeypatch):
    client, seen = _client(monkeypatch, _settings(model_boundary_service_token=""), fail=True)
    response = _post(client, {"caseId": CASE}, headers=_auth_headers())
    assert response.status_code == 401
    assert response.content == b""
    assert seen["runs"] == []


def test_unknown_case_id_is_422_and_does_not_run_the_workflow(monkeypatch):
    client, seen = _client(monkeypatch, _settings(), fail=True)
    response = _post(client, {"caseId": "SYN-FOLLOWUP-999"}, headers=_auth_headers())
    assert response.status_code == 422
    assert seen["runs"] == []


def test_missing_case_id_is_422(monkeypatch):
    client, seen = _client(monkeypatch, _settings(), fail=True)
    response = _post(client, {}, headers=_auth_headers())
    assert response.status_code == 422
    assert seen["runs"] == []


def test_extra_field_is_rejected(monkeypatch):
    client, seen = _client(monkeypatch, _settings(), fail=True)
    response = _post(client, {"caseId": CASE, "extra": "no"}, headers=_auth_headers())
    assert response.status_code == 422
    assert seen["runs"] == []


def test_external_patient_id_is_rejected(monkeypatch):
    client, seen = _client(monkeypatch, _settings(), fail=True)
    response = _post(
        client,
        {"caseId": CASE, "patientId": "external-id"},
        headers=_auth_headers(),
    )
    assert response.status_code == 422
    assert seen["runs"] == []


def test_bundle_is_rejected_before_the_workflow(monkeypatch):
    client, seen = _client(monkeypatch, _settings(), fail=True)
    response = _post(
        client,
        {"resourceType": "Bundle", "type": "collection", "entry": []},
        headers=_auth_headers(),
    )
    assert response.status_code == 422
    assert seen["runs"] == []


def test_completed_case_projects_the_workflow_result(monkeypatch):
    client, seen = _client(
        monkeypatch,
        _settings(),
        _result("finish", "Synthetic answer.", follow_up_required="true"),
    )
    response = _post(client, {"caseId": CASE}, headers=_auth_headers())
    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "completed"
    assert body["caseId"] == CASE
    assert body["runId"]
    assert body["followUpRequired"] == "true"
    assert body["answer"] == "Synthetic answer."
    assert body["evidence"] == [
        {"tool": "get_patient_followup_context", "id": "Patient/SYN-PATIENT-001"},
        {"tool": "get_patient_followup_context", "id": "Observation/obs-synthetic-001"},
    ]
    assert FORBIDDEN_BODY_KEYS.isdisjoint(body)
    assert "SYN-PATIENT-001" in response.text
    assert "valueString" not in response.text
    assert "thought_signature" not in response.text
    workflow = seen["runs"][0]
    assert workflow.cases == [CASE]


def test_denied_result_stays_denied(monkeypatch):
    client, _seen = _client(
        monkeypatch,
        _settings(),
        _result("denied", "Tool denied by policy", evidence=[], follow_up_required="unknown"),
    )
    response = _post(client, {"caseId": CASE}, headers=_auth_headers())
    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "denied"
    assert body["answer"] == "Tool denied by policy"
    assert body["evidence"] == []


def test_unavailable_result_is_not_completed(monkeypatch):
    client, _seen = _client(
        monkeypatch,
        _settings(),
        _result("unavailable", "stopped: clinical context unavailable", evidence=[]),
    )
    response = _post(client, {"caseId": CASE}, headers=_auth_headers())
    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "unavailable"
    assert body["status"] != "completed"


def test_limit_result_stays_limit(monkeypatch):
    client, _seen = _client(
        monkeypatch,
        _settings(),
        _result("limit", "stopped: model turn limit reached", evidence=[]),
    )
    response = _post(client, {"caseId": CASE}, headers=_auth_headers())
    assert response.status_code == 200
    assert response.json()["status"] == "limit"


def test_http_run_id_is_the_workflow_run_id(monkeypatch):
    monkeypatch.setattr("app.followup_service.uuid.uuid4", lambda: uuid.UUID("12345678123456781234567812345678"))
    client, seen = _client(monkeypatch, _settings(), _result("finish", "Synthetic answer."))
    response = _post(client, {"caseId": CASE}, headers=_auth_headers())
    body = response.json()
    assert body["runId"] == "12345678-1234-5678-1234-567812345678"
    assert seen["runs"][0].run_id == body["runId"]
    assert body["runId"] != "ignored-by-the-script"


def test_http_run_id_matches_the_policy_audit_log(monkeypatch, caplog):
    fixed = uuid.UUID("12345678123456781234567812345678")
    monkeypatch.setattr("app.followup_service.uuid.uuid4", lambda: fixed)
    sink = InMemoryAuditSink()
    replies = [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "get_patient_followup_context",
                    "args": {"case_id": CASE},
                    "id": "call-1",
                    "type": "tool_call",
                }
            ],
        ),
        AIMessage(content="Context received from the model."),
    ]

    def factory(run_id: str) -> FollowUpWorkflow:
        return FollowUpWorkflow(
            model=lambda _messages: replies.pop(0),
            sink=sink,
            fhir_client=PreparedReadClient(),
            clock=lambda: "2026-09-25T00:00:03Z",
            run_id=run_id,
        )

    monkeypatch.setattr("app.followup_service.build_followup_workflow", factory)
    app.dependency_overrides[get_settings] = lambda: _settings()
    with caplog.at_level(logging.INFO, logger="ai-service"):
        response = _post(TestClient(app), {"caseId": CASE}, headers=_auth_headers())
    body = response.json()
    assert response.status_code == 200
    assert set(body) == {"runId", "caseId", "status", "followUpRequired", "answer", "evidence"}
    assert body["runId"] == "12345678-1234-5678-1234-567812345678"
    assert body["caseId"] == CASE
    assert body["status"] == "completed"
    assert "followup_tool_policy_audit" not in response.text
    assert POLICY_VERSION not in response.text
    assert "thought_signature" not in response.text
    event = sink.events[0]
    assert event.run_id == body["runId"]
    assert event.case_id == body["caseId"]
    assert event.tool_name == "get_patient_followup_context"
    assert event.decision == "allowed"
    lines = [
        record.getMessage()
        for record in caplog.records
        if record.getMessage().startswith("followup_tool_policy_audit ")
    ]
    assert lines == [
        "followup_tool_policy_audit "
        f"run_id={body['runId']} case_id={CASE} "
        "tool_name=get_patient_followup_context decision=allowed "
        f"policy_version={POLICY_VERSION} reason=read tool is allowed"
    ]
    for token in (
        "thought_signature",
        "gemini_api_key",
        "x-service-token",
        "authorization",
        "Patient",
        "Observation",
        "Synthetic observation result",
        "valueString",
        "prompt",
        "completion",
        "args=",
    ):
        assert token not in lines[0]


class _DecisionPart:
    function_call = None
    thought_signature = None

    def __init__(self, text: str) -> None:
        self.text = text


class _DecisionResponse:
    parsed = None

    def __init__(self, text: str) -> None:
        self.candidates = [
            type("Candidate", (), {"content": type("Content", (), {"parts": [_DecisionPart(text)]})()})()
        ]


def _post_real_workflow(monkeypatch, final: AIMessage):
    replies = [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "get_patient_followup_context",
                    "args": {"case_id": CASE},
                    "id": "call-1",
                    "type": "tool_call",
                }
            ],
        ),
        final,
    ]

    def factory(run_id: str) -> FollowUpWorkflow:
        return FollowUpWorkflow(
            model=lambda _messages: replies.pop(0),
            sink=InMemoryAuditSink(),
            fhir_client=PreparedReadClient(),
            clock=lambda: "2026-09-25T00:00:03Z",
            run_id=run_id,
        )

    monkeypatch.setattr("app.followup_service.build_followup_workflow", factory)
    app.dependency_overrides[get_settings] = lambda: _settings()
    return _post(TestClient(app), {"caseId": CASE}, headers=_auth_headers())


@pytest.mark.parametrize(
    ("token", "answer"),
    [("true", "Needs a synthetic follow-up."), ("false", "No follow-up is needed.")],
)
def test_http_projects_a_structured_follow_up_required(monkeypatch, token, answer):
    message = followup_message_from_response(
        _DecisionResponse('{"answer": "%s", "follow_up_required": "%s"}' % (answer, token))
    )
    response = _post_real_workflow(monkeypatch, message)
    body = response.json()
    assert response.status_code == 200
    assert set(body) == {"runId", "caseId", "status", "followUpRequired", "answer", "evidence"}
    assert body["status"] == "completed"
    assert body["followUpRequired"] == token
    assert body["answer"] == answer
    assert "thought_signature" not in response.text


def test_http_keeps_follow_up_required_unknown_when_the_model_omits_it(monkeypatch):
    prose = "The text says follow-up is true because an observation exists."
    response = _post_real_workflow(monkeypatch, AIMessage(content=prose))
    body = response.json()
    assert response.status_code == 200
    assert set(body) == {"runId", "caseId", "status", "followUpRequired", "answer", "evidence"}
    assert body["followUpRequired"] == "unknown"
    assert body["answer"] == prose


def test_http_response_does_not_include_a_trace(monkeypatch):
    client, _seen = _client(monkeypatch, _settings(), _result("finish", "Synthetic answer."))
    response = _post(client, {"caseId": CASE}, headers=_auth_headers())
    body = response.json()
    assert response.status_code == 200
    assert "trace" not in body
    assert "events" not in body


def test_workflow_exception_is_http_502_without_the_exception_text(monkeypatch):
    def factory(run_id: str):
        class _Broken:
            def run(self, case_id: str):
                raise RuntimeError("GEMINI_API_KEY=secret Patient/SYN-PATIENT-001")

        return _Broken()

    monkeypatch.setattr("app.followup_service.build_followup_workflow", factory)
    app.dependency_overrides[get_settings] = lambda: _settings()
    response = _post(TestClient(app), {"caseId": CASE}, headers=_auth_headers())
    assert response.status_code == 502
    assert response.json() == {"detail": "Follow-up workflow failed"}
    assert "secret" not in response.text
    assert "Patient" not in response.text
    assert "completed" not in response.text


def test_disabled_flag_with_valid_token_is_503_and_does_not_run_the_workflow(monkeypatch):
    client, seen = _client(monkeypatch, _settings(followup_agent_enabled=False), fail=True)
    response = _post(client, {"not": "a valid request"}, headers=_auth_headers())
    assert response.status_code == 503
    assert response.json() == {"detail": "Follow-up agent is disabled"}
    assert seen["runs"] == []


def test_disabled_flag_with_invalid_token_is_401(monkeypatch):
    client, seen = _client(monkeypatch, _settings(followup_agent_enabled=False), fail=True)
    response = _post(client, {"caseId": CASE}, headers={"X-Service-Token": "wrong"})
    assert response.status_code == 401
    assert response.content == b""
    assert seen["runs"] == []


def test_disabled_flag_with_missing_token_is_401(monkeypatch):
    client, seen = _client(monkeypatch, _settings(followup_agent_enabled=False), fail=True)
    response = _post(client, {"caseId": CASE}, headers={})
    assert response.status_code == 401
    assert response.content == b""
    assert seen["runs"] == []


def test_health_ignores_the_followup_flag():
    app.dependency_overrides[get_settings] = lambda: _settings(followup_agent_enabled=False)
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_followup_flag_defaults_false_and_is_independent(monkeypatch):
    monkeypatch.delenv("FOLLOWUP_AGENT_ENABLED", raising=False)
    monkeypatch.setenv("LLM_EXPERIMENTAL_ENABLED", "true")
    settings = Settings.from_env()
    assert settings.followup_agent_enabled is False
    assert settings.llm_experimental_enabled is True

    monkeypatch.setenv("FOLLOWUP_AGENT_ENABLED", "true")
    monkeypatch.setenv("LLM_EXPERIMENTAL_ENABLED", "false")
    enabled = Settings.from_env()
    assert enabled.followup_agent_enabled is True
    assert enabled.llm_experimental_enabled is False
