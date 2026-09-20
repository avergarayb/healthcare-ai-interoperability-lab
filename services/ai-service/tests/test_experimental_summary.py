from __future__ import annotations

import copy
import logging

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings
from app.experimental_fixture import CANONICAL_FIXTURE
from app.experimental_models import ExperimentalSummaryResponse
from app.fake_llm_provider import FakeLLMProvider
from app.main import app, get_llm_provider, get_settings


def _settings(**overrides) -> Settings:
    values = {
        "model_boundary_base_url": "http://model-boundary.test",
        "model_boundary_path": "/api/model-boundary/v1",
        "model_boundary_timeout_seconds": 5,
        "model_boundary_service_token": "test-model-boundary-token",
        "host": "127.0.0.1",
        "port": 8090,
        "llm_experimental_enabled": True,
        "gemini_api_key": "test-gemini-key",
        "gemini_model": "gemini-2.5-flash",
    }
    values.update(overrides)
    return Settings(**values)


def _client(settings: Settings, provider: FakeLLMProvider | None = None) -> TestClient:
    app.dependency_overrides[get_settings] = lambda: settings
    if provider is not None:
        app.dependency_overrides[get_llm_provider] = lambda: provider
    return TestClient(app)


def _auth_headers() -> dict[str, str]:
    return {
        "X-Service-Token": "test-model-boundary-token",
        "X-Correlation-ID": "corr-076",
    }


def _post(client: TestClient, payload, headers=None):
    return client.post("/internal/experimental-summary", json=payload, headers=headers)


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


def test_missing_service_token_is_401():
    provider = FakeLLMProvider()
    client = _client(_settings(), provider)
    response = _post(client, CANONICAL_FIXTURE, headers={})
    assert response.status_code == 401
    assert response.content == b""
    assert provider.calls == 0


def test_invalid_service_token_is_401():
    provider = FakeLLMProvider()
    client = _client(_settings(), provider)
    response = _post(client, CANONICAL_FIXTURE, headers={"X-Service-Token": "wrong"})
    assert response.status_code == 401
    assert provider.calls == 0


def test_blank_configured_token_is_fail_closed():
    provider = FakeLLMProvider()
    client = _client(_settings(model_boundary_service_token=""), provider)
    response = _post(client, CANONICAL_FIXTURE, headers=_auth_headers())
    assert response.status_code == 401
    assert provider.calls == 0


def test_disabled_flag_is_503_and_does_not_call_provider():
    provider = FakeLLMProvider()
    client = _client(_settings(llm_experimental_enabled=False), provider)
    response = _post(client, CANONICAL_FIXTURE, headers=_auth_headers())
    assert response.status_code == 503
    assert response.json() == {
        "status": "DISABLED",
        "summary": None,
        "provider": "GEMINI",
        "model": "gemini-2.5-flash",
        "promptVersion": "experimental-summary-v1",
        "modelCalled": False,
        "requiresHumanReview": True,
    }
    assert provider.calls == 0


def test_disabled_flag_does_not_validate_body_before_gate():
    provider = FakeLLMProvider()
    client = _client(_settings(llm_experimental_enabled=False), provider)
    response = _post(client, {"not": "canonical"}, headers=_auth_headers())
    assert response.status_code == 503
    assert response.json()["status"] == "DISABLED"
    assert response.json()["modelCalled"] is False
    assert provider.calls == 0


def test_valid_synthetic_request_completes():
    provider = FakeLLMProvider("success")
    client = _client(_settings(), provider)
    response = _post(client, CANONICAL_FIXTURE, headers=_auth_headers())
    assert response.status_code == 200
    body = response.json()
    assert body == {
        "status": "COMPLETED",
        "summary": "Synthetic laboratory summary for SYN-076-001.",
        "provider": "GEMINI",
        "model": "gemini-2.5-flash",
        "promptVersion": "experimental-summary-v1",
        "modelCalled": True,
        "requiresHumanReview": True,
    }
    assert provider.calls == 1


def test_unknown_field_is_422():
    provider = FakeLLMProvider()
    payload = copy.deepcopy(CANONICAL_FIXTURE)
    payload["extra"] = "no"
    client = _client(_settings(), provider)
    response = _post(client, payload, headers=_auth_headers())
    assert response.status_code == 422
    assert response.json()["status"] == "VALIDATION_ERROR"
    assert response.json()["modelCalled"] is False
    assert response.json()["requiresHumanReview"] is True
    assert provider.calls == 0


def test_bundle_is_rejected():
    provider = FakeLLMProvider()
    client = _client(_settings(), provider)
    response = _post(
        client,
        {"resourceType": "Bundle", "type": "collection", "entry": []},
        headers=_auth_headers(),
    )
    assert response.status_code == 422
    assert response.json()["modelCalled"] is False
    assert provider.calls == 0


def test_token_like_input_is_rejected():
    provider = FakeLLMProvider()
    payload = copy.deepcopy(CANONICAL_FIXTURE)
    payload["access_token"] = "secret"
    client = _client(_settings(), provider)
    response = _post(client, payload, headers=_auth_headers())
    assert response.status_code == 422
    assert provider.calls == 0


def test_missing_required_field_is_rejected():
    provider = FakeLLMProvider()
    payload = copy.deepcopy(CANONICAL_FIXTURE)
    payload.pop("caseId")
    client = _client(_settings(), provider)
    response = _post(client, payload, headers=_auth_headers())
    assert response.status_code == 422
    assert provider.calls == 0


def test_non_canonical_case_id_is_rejected():
    provider = FakeLLMProvider()
    payload = copy.deepcopy(CANONICAL_FIXTURE)
    payload["caseId"] = "SYN-076-002"
    client = _client(_settings(), provider)
    response = _post(client, payload, headers=_auth_headers())
    assert response.status_code == 422
    assert provider.calls == 0


def test_changed_fixture_field_is_rejected():
    provider = FakeLLMProvider()
    payload = copy.deepcopy(CANONICAL_FIXTURE)
    payload["sex"] = "M"
    client = _client(_settings(), provider)
    response = _post(client, payload, headers=_auth_headers())
    assert response.status_code == 422
    assert provider.calls == 0


def test_missing_gemini_key_is_503_without_invocation():
    provider = FakeLLMProvider()
    client = _client(_settings(gemini_api_key=""), provider)
    response = _post(client, CANONICAL_FIXTURE, headers=_auth_headers())
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "PROVIDER_ERROR"
    assert body["modelCalled"] is False
    assert body["requiresHumanReview"] is True
    assert provider.calls == 0


def test_provider_timeout_is_504_and_model_called_true():
    provider = FakeLLMProvider("timeout")
    client = _client(_settings(), provider)
    response = _post(client, CANONICAL_FIXTURE, headers=_auth_headers())
    assert response.status_code == 504
    assert response.json()["status"] == "PROVIDER_ERROR"
    assert response.json()["modelCalled"] is True
    assert response.json()["summary"] is None
    assert provider.calls == 1


def test_provider_4xx_is_502():
    provider = FakeLLMProvider("http_4xx")
    client = _client(_settings(), provider)
    response = _post(client, CANONICAL_FIXTURE, headers=_auth_headers())
    assert response.status_code == 502
    assert response.json()["modelCalled"] is True


def test_provider_5xx_is_502():
    provider = FakeLLMProvider("http_5xx")
    client = _client(_settings(), provider)
    response = _post(client, CANONICAL_FIXTURE, headers=_auth_headers())
    assert response.status_code == 502
    assert response.json()["modelCalled"] is True


def test_malformed_provider_response_is_502():
    provider = FakeLLMProvider("malformed")
    client = _client(_settings(), provider)
    response = _post(client, CANONICAL_FIXTURE, headers=_auth_headers())
    assert response.status_code == 502
    assert response.json()["modelCalled"] is True


def test_empty_provider_response_is_502():
    provider = FakeLLMProvider("empty")
    client = _client(_settings(), provider)
    response = _post(client, CANONICAL_FIXTURE, headers=_auth_headers())
    assert response.status_code == 502
    assert response.json()["modelCalled"] is True


def test_oversized_summary_is_rejected():
    provider = FakeLLMProvider("oversized")
    client = _client(_settings(), provider)
    response = _post(client, CANONICAL_FIXTURE, headers=_auth_headers())
    assert response.status_code == 502
    assert response.json()["summary"] is None
    assert response.json()["modelCalled"] is True


def test_provider_cannot_override_governance_fields():
    provider = FakeLLMProvider("unexpected")
    client = _client(_settings(), provider)
    response = _post(client, CANONICAL_FIXTURE, headers=_auth_headers())
    assert response.status_code == 502
    assert response.json()["requiresHumanReview"] is True
    assert response.json()["modelCalled"] is True


def test_requires_human_review_cannot_be_false():
    with pytest.raises(ValidationError):
        ExperimentalSummaryResponse(
            status="COMPLETED",
            summary="x",
            provider="GEMINI",
            model="gemini-2.5-flash",
            promptVersion="experimental-summary-v1",
            modelCalled=True,
            requiresHumanReview=False,
        )


def test_agent_context_contract_unchanged(settings, valid_contract, monkeypatch):
    def fake_fetch(current_settings, client=None):
        import json

        return __import__("app.consumer", fromlist=["BoundaryResponse"]).BoundaryResponse(
            kind="http",
            status_code=200,
            body_text=json.dumps(valid_contract),
        )

    monkeypatch.setattr("app.consumer.fetch_contract", fake_fetch)
    app.dependency_overrides[get_settings] = lambda: settings
    response = TestClient(app).get(
        "/internal/agent-context", headers={"X-Service-Token": "test-model-boundary-token"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "received"
    assert response.json()["modelCalled"] is False


def test_logs_do_not_contain_secrets_or_prompt(caplog):
    provider = FakeLLMProvider("success")
    client = _client(_settings(), provider)
    with caplog.at_level(logging.INFO, logger="ai-service"):
        response = _post(client, CANONICAL_FIXTURE, headers=_auth_headers())
    assert response.status_code == 200
    text = caplog.text
    assert "experimental_llm_call" in text
    assert "modelCalled=true" in text
    assert "promptVersion=experimental-summary-v1" in text
    assert "test-gemini-key" not in text
    assert "test-model-boundary-token" not in text
    assert "Do not diagnose" not in text
    assert "Synthetic laboratory summary" not in text
    assert "Synthetic observation A" not in text
