"""Follow-up does not resolve GeminiProvider. Auth and the feature flag still come first."""

from __future__ import annotations

import inspect

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.gemini_provider import GeminiProvider
from app.main import app, get_settings


CASE = "SYN-FOLLOWUP-001"


def _settings(**overrides) -> Settings:
    values = {
        "model_boundary_base_url": "http://model-boundary.test",
        "model_boundary_path": "/api/model-boundary/v1",
        "model_boundary_timeout_seconds": 5,
        "model_boundary_service_token": "test-model-boundary-token",
        "host": "127.0.0.1",
        "port": 8090,
        "llm_experimental_enabled": False,
        "gemini_api_key": "configured-gemini-key",
        "gemini_model": "gemini-flash-latest",
        "followup_agent_enabled": False,
    }
    values.update(overrides)
    return Settings(**values)


def _auth_headers() -> dict[str, str]:
    return {"X-Service-Token": "test-model-boundary-token"}


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


def _spy(monkeypatch, provider=None):
    calls = {"count": 0}

    def factory(settings=None):
        calls["count"] += 1
        if provider is None:
            raise AssertionError("provider factory must not be called")
        return provider

    monkeypatch.setattr("app.main.get_llm_provider", factory)
    return calls


def _post(payload, settings: Settings, headers):
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app).post("/internal/agent/follow-up", json=payload, headers=headers)


def test_disabled_with_configured_key_does_not_resolve_provider(monkeypatch):
    calls = _spy(monkeypatch)
    response = _post({"caseId": CASE}, _settings(), _auth_headers())
    assert response.status_code == 503
    assert response.json() == {"detail": "Follow-up agent is disabled"}
    assert calls["count"] == 0


def test_disabled_malformed_body_does_not_resolve_provider(monkeypatch):
    calls = _spy(monkeypatch)
    response = _post({"resourceType": "Bundle"}, _settings(), _auth_headers())
    assert response.status_code == 503
    assert calls["count"] == 0


def test_invalid_token_does_not_resolve_provider_when_enabled(monkeypatch):
    calls = _spy(monkeypatch)
    response = _post(
        {"caseId": CASE},
        _settings(followup_agent_enabled=True),
        {"X-Service-Token": "wrong"},
    )
    assert response.status_code == 401
    assert response.content == b""
    assert calls["count"] == 0


def test_enabled_valid_request_runs_the_workflow_and_not_the_summary_provider(monkeypatch):
    from app.langgraph_followup_workflow import FollowUpWorkflowResult

    calls = _spy(monkeypatch)
    runs: list[str] = []

    class _Workflow:
        def __init__(self, run_id: str) -> None:
            self.run_id = run_id

        def run(self, case_id: str) -> FollowUpWorkflowResult:
            runs.append(case_id)
            return FollowUpWorkflowResult(
                case_id=case_id,
                status="finish",
                final_answer="Synthetic answer.",
                patient=None,
                observations=[],
                evidence=[],
                tools_used=[],
                turns=1,
                run_id=self.run_id,
                follow_up_required="unknown",
            )

    monkeypatch.setattr("app.followup_service.build_followup_workflow", lambda run_id: _Workflow(run_id))
    response = _post({"caseId": CASE}, _settings(followup_agent_enabled=True), _auth_headers())
    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "completed"
    assert body["answer"] == "Synthetic answer."
    assert calls["count"] == 0
    assert runs == [CASE]


def test_enabled_malformed_body_does_not_resolve_provider(monkeypatch):
    calls = _spy(monkeypatch)
    response = _post({"extra": "no"}, _settings(followup_agent_enabled=True), _auth_headers())
    assert response.status_code == 422
    assert calls["count"] == 0


def test_health_does_not_resolve_provider(monkeypatch):
    calls = _spy(monkeypatch)
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert calls["count"] == 0


def test_gemini_provider_does_not_execute_tools():
    source = inspect.getsource(GeminiProvider)
    assert "ToolRegistry" not in source
    assert "get_patient" not in source
    assert "generate_content" in inspect.getsource(GeminiProvider._invoke)


def test_enabled_endpoint_does_not_call_generate_text(monkeypatch):
    from app.langgraph_followup_workflow import FollowUpWorkflowResult

    assert not hasattr(GeminiProvider, "generate_text")

    class _Workflow:
        def __init__(self, run_id: str) -> None:
            self.run_id = run_id

        def run(self, case_id: str) -> FollowUpWorkflowResult:
            return FollowUpWorkflowResult(
                case_id=case_id,
                status="finish",
                final_answer="Synthetic answer.",
                patient=None,
                observations=[],
                evidence=[],
                tools_used=[],
                turns=1,
                run_id=self.run_id,
                follow_up_required="unknown",
            )

    monkeypatch.setattr("app.followup_service.build_followup_workflow", lambda run_id: _Workflow(run_id))
    response = _post({"caseId": CASE}, _settings(followup_agent_enabled=True), _auth_headers())
    assert response.status_code == 200
    assert response.json()["status"] == "completed"
