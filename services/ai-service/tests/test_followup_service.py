from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.fake_llm_provider import FakeLLMProvider
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
        "gemini_api_key": "",
        "gemini_model": "gemini-flash-latest",
        "followup_agent_enabled": True,
    }
    values.update(overrides)
    return Settings(**values)


def _client(settings: Settings, provider: FakeLLMProvider | None) -> TestClient:
    import app.main as main

    app.dependency_overrides[get_settings] = lambda: settings
    main.get_llm_provider = lambda settings=None, _provider=provider: _provider
    return TestClient(app)


def _auth_headers() -> dict[str, str]:
    return {
        "X-Service-Token": "test-model-boundary-token",
        "X-Correlation-ID": "corr-followup",
    }


def _post(client: TestClient, payload, headers=None):
    return client.post("/internal/agent/follow-up", json=payload, headers=headers)


def _tool_call(tool: str) -> dict:
    return {"type": "tool_call", "tool": tool, "arguments": {"caseId": CASE}}


def _final(*, evidence=None) -> dict:
    return {
        "type": "final",
        "output": {
            "followUpRequired": "true",
            "summary": "Synthetic follow-up summary.",
            "reason": "Synthetic reason.",
            "suggestedActions": [{"type": "review", "detail": "Synthetic review"}],
            "evidence": evidence or [],
            "requiresHumanReview": True,
        },
    }


@pytest.fixture(autouse=True)
def _clear_overrides():
    import app.main as main

    original_provider = main.get_llm_provider
    yield
    main.get_llm_provider = original_provider
    app.dependency_overrides.clear()


def test_health_stays_unauthenticated():
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_missing_service_token_is_401_and_does_not_call_provider():
    provider = FakeLLMProvider(script=[_final()])
    client = _client(_settings(), provider)
    response = _post(client, {"caseId": CASE}, headers={})
    assert response.status_code == 401
    assert response.content == b""
    assert provider.calls == 0
    assert "test-model-boundary-token" not in response.text


def test_invalid_service_token_is_401_and_does_not_call_provider():
    provider = FakeLLMProvider(script=[_final()])
    client = _client(_settings(), provider)
    response = _post(client, {"caseId": CASE}, headers={"X-Service-Token": "wrong"})
    assert response.status_code == 401
    assert response.content == b""
    assert provider.calls == 0


def test_blank_configured_token_is_fail_closed():
    provider = FakeLLMProvider(script=[_final()])
    client = _client(_settings(model_boundary_service_token=""), provider)
    response = _post(client, {"caseId": CASE}, headers=_auth_headers())
    assert response.status_code == 401
    assert response.content == b""
    assert provider.calls == 0


def test_valid_token_reaches_the_agent():
    provider = FakeLLMProvider(script=[_final()])
    client = _client(_settings(), provider)
    response = _post(client, {"caseId": CASE}, headers=_auth_headers())
    assert response.status_code == 200
    assert response.json()["status"] == "COMPLETED"
    assert provider.calls == 1


def test_valid_case_id_returns_follow_up_contract():
    provider = FakeLLMProvider(script=[_final()])
    client = _client(_settings(), provider)
    response = _post(client, {"caseId": "SYN-FOLLOWUP-003"}, headers=_auth_headers())
    body = response.json()
    assert response.status_code == 200
    assert body["caseId"] == "SYN-FOLLOWUP-003"
    assert body["agent"] == "follow-up-agent"
    assert body["requiresHumanReview"] is True
    assert body["modelCalled"] is True
    assert "runId" in body
    assert "followUpRequired" in body
    assert "suggestedActions" in body
    assert "evidence" in body


def test_unknown_case_id_is_422_and_does_not_call_provider():
    provider = FakeLLMProvider(script=[_final()])
    client = _client(_settings(), provider)
    response = _post(client, {"caseId": "SYN-FOLLOWUP-999"}, headers=_auth_headers())
    assert response.status_code == 422
    assert provider.calls == 0


def test_missing_case_id_is_422():
    provider = FakeLLMProvider(script=[_final()])
    client = _client(_settings(), provider)
    response = _post(client, {}, headers=_auth_headers())
    assert response.status_code == 422
    assert provider.calls == 0


def test_extra_field_is_rejected():
    provider = FakeLLMProvider(script=[_final()])
    client = _client(_settings(), provider)
    response = _post(client, {"caseId": CASE, "extra": "no"}, headers=_auth_headers())
    assert response.status_code == 422
    assert provider.calls == 0


def test_external_patient_id_is_rejected():
    provider = FakeLLMProvider(script=[_final()])
    client = _client(_settings(), provider)
    response = _post(
        client,
        {"caseId": CASE, "patientId": "external-id"},
        headers=_auth_headers(),
    )
    assert response.status_code == 422
    assert provider.calls == 0


def test_bundle_is_rejected_before_the_agent():
    provider = FakeLLMProvider(script=[_final()])
    client = _client(_settings(), provider)
    response = _post(
        client,
        {"resourceType": "Bundle", "type": "collection", "entry": []},
        headers=_auth_headers(),
    )
    assert response.status_code == 422
    assert provider.calls == 0


def test_final_without_tools_is_http_200():
    provider = FakeLLMProvider(script=[_final()])
    client = _client(_settings(), provider)
    response = _post(client, {"caseId": CASE}, headers=_auth_headers())
    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "COMPLETED"
    assert body["modelCalled"] is True
    assert body["requiresHumanReview"] is True
    assert body["evidence"] == []
    assert body["summary"] == "Synthetic follow-up summary."


def test_one_tool_then_final_is_http_200():
    provider = FakeLLMProvider(
        script=[
            _tool_call("get_patient"),
            _final(evidence=[{"tool": "get_patient", "id": "SYN-PAT-001"}]),
        ]
    )
    client = _client(_settings(), provider)
    response = _post(client, {"caseId": CASE}, headers=_auth_headers())
    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "COMPLETED"
    assert body["modelCalled"] is True
    assert body["requiresHumanReview"] is True
    assert body["evidence"] == [{"tool": "get_patient", "id": "SYN-PAT-001"}]
    assert provider.calls == 2


def test_multiple_tools_then_final_is_http_200():
    provider = FakeLLMProvider(
        script=[
            _tool_call("get_upcoming_appointments"),
            _tool_call("get_recent_encounters"),
            _final(
                evidence=[
                    {"tool": "get_upcoming_appointments", "id": "SYN-APT-001"},
                    {"tool": "get_recent_encounters", "id": "SYN-ENC-001"},
                ]
            ),
        ]
    )
    client = _client(_settings(), provider)
    response = _post(client, {"caseId": CASE}, headers=_auth_headers())
    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "COMPLETED"
    assert body["requiresHumanReview"] is True
    assert body["modelCalled"] is True
    assert {item["id"] for item in body["evidence"]} == {"SYN-APT-001", "SYN-ENC-001"}
    assert provider.calls == 3


def test_send_message_is_policy_denied_without_tool_execution(monkeypatch):
    from app.followup_tools import ToolRegistry, ToolSpec, build_followup_tool_registry

    def must_not_run(payload):
        raise AssertionError("tool must not run after policy deny")

    def guarded_registry() -> ToolRegistry:
        source = build_followup_tool_registry()
        registry = ToolRegistry()
        for name in source.names():
            spec = source.get(name)
            registry.register(
                ToolSpec(
                    name=spec.name,
                    description=spec.description,
                    resources=spec.resources,
                    fn=must_not_run,
                )
            )
        return registry

    monkeypatch.setattr("app.followup_runtime.build_followup_tool_registry", guarded_registry)
    provider = FakeLLMProvider(script=[_tool_call("send_message")])
    client = _client(_settings(), provider)
    response = _post(client, {"caseId": CASE}, headers=_auth_headers())
    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "POLICY_DENIED"
    assert "send_message" in body["reason"]
    assert body["requiresHumanReview"] is True
    assert provider.calls == 1


def test_provider_error_is_http_200_application_status(monkeypatch):
    monkeypatch.setattr("app.followup_runtime.time.sleep", lambda _seconds: None)
    provider = FakeLLMProvider("http_5xx")
    client = _client(_settings(), provider)
    response = _post(client, {"caseId": CASE}, headers=_auth_headers())
    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "PROVIDER_ERROR"
    assert body["modelCalled"] is True
    assert body["requiresHumanReview"] is True
    assert provider.calls == 2


def test_disabled_flag_with_valid_token_is_503_and_does_not_run_the_agent(monkeypatch):
    def must_not_run(*args, **kwargs):
        raise AssertionError("agent must not run while disabled")

    monkeypatch.setattr("app.followup_service.run_followup_agent", must_not_run)
    monkeypatch.setattr("app.followup_fixtures.get_followup_fixture", must_not_run)
    provider = FakeLLMProvider(script=[_final()])
    client = _client(_settings(followup_agent_enabled=False), provider)
    response = _post(client, {"not": "a valid request"}, headers=_auth_headers())
    assert response.status_code == 503
    assert response.json() == {"detail": "Follow-up agent is disabled"}
    assert provider.calls == 0


def test_disabled_flag_with_invalid_token_is_401():
    provider = FakeLLMProvider(script=[_final()])
    client = _client(_settings(followup_agent_enabled=False), provider)
    response = _post(client, {"caseId": CASE}, headers={"X-Service-Token": "wrong"})
    assert response.status_code == 401
    assert response.content == b""
    assert provider.calls == 0


def test_disabled_flag_with_missing_token_is_401():
    provider = FakeLLMProvider(script=[_final()])
    client = _client(_settings(followup_agent_enabled=False), provider)
    response = _post(client, {"caseId": CASE}, headers={})
    assert response.status_code == 401
    assert response.content == b""
    assert provider.calls == 0


def test_enabled_flag_with_valid_token_runs_the_current_flow():
    provider = FakeLLMProvider(script=[_final()])
    client = _client(_settings(followup_agent_enabled=True, llm_experimental_enabled=False), provider)
    response = _post(client, {"caseId": CASE}, headers=_auth_headers())
    assert response.status_code == 200
    assert response.json()["status"] == "COMPLETED"
    assert response.json()["requiresHumanReview"] is True
    assert provider.calls == 1


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
