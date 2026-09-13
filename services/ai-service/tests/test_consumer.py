from __future__ import annotations

import json
from typing import Any

import httpx
from fastapi.testclient import TestClient

from app.consumer import BoundaryResponse, consume, evaluate
from app.main import app, get_settings
from app.models import RESULT_FIELDS
from tests.conftest import collection, contract, empty_contract


def _http(status_code: int, payload: Any | None = None, text: str | None = None) -> BoundaryResponse:
    if text is not None:
        body = text
    elif payload is None:
        body = ""
    else:
        body = json.dumps(payload)
    return BoundaryResponse(kind="http", status_code=status_code, body_text=body)


def _assert_shape(result) -> None:
    dumped = result.model_dump()
    assert tuple(dumped.keys()) == RESULT_FIELDS
    assert result.modelCalled is False


def test_complete_with_retained_context_is_received(valid_contract):
    result = evaluate(_http(200, valid_contract))
    _assert_shape(result)
    assert result.status == "received"
    assert result.contractVersion == "v1"
    assert result.outcome == "SNAPSHOT_COMPLETE"
    assert result.reason is None


def test_partial_with_retained_context_is_received():
    result = evaluate(_http(200, contract(outcome="SNAPSHOT_PARTIAL")))
    assert result.status == "received"
    assert result.outcome == "SNAPSHOT_PARTIAL"
    assert result.reason is None
    assert result.modelCalled is False


def test_empty_context_is_rejected():
    result = evaluate(_http(200, empty_contract()))
    assert result.status == "rejected"
    assert result.reason == "empty_context"
    assert result.outcome == "SNAPSHOT_COMPLETE"
    assert result.modelCalled is False


def test_null_medication_requests_is_valid_and_can_be_empty():
    payload = empty_contract()
    assert payload["medicationRequests"] is None
    result = evaluate(_http(200, payload))
    assert result.reason == "empty_context"


def test_missing_medication_requests_key_is_invalid():
    payload = contract(omit=("medicationRequests",))
    result = evaluate(_http(200, payload))
    assert result.status == "rejected"
    assert result.reason == "invalid_contract"
    assert result.contractVersion is None
    assert result.outcome is None


def test_unavailable_outcome_on_http_200_is_rejected():
    result = evaluate(_http(200, empty_contract(outcome="SNAPSHOT_UNAVAILABLE")))
    assert result.status == "rejected"
    assert result.reason == "boundary_outcome_not_success"
    assert result.outcome == "SNAPSHOT_UNAVAILABLE"
    assert result.modelCalled is False


def test_http_4xx_does_not_parse_body():
    result = evaluate(_http(401, empty_contract(outcome="AUTHENTICATION_REQUIRED")))
    assert result.status == "rejected"
    assert result.reason == "boundary_http_4xx"
    assert result.contractVersion is None
    assert result.outcome is None


def test_http_5xx_does_not_parse_body():
    result = evaluate(_http(502, empty_contract(outcome="SNAPSHOT_UNAVAILABLE")))
    assert result.reason == "boundary_http_5xx"
    assert result.contractVersion is None


def test_invalid_json_is_rejected():
    result = evaluate(_http(200, text="{not-json"))
    assert result.reason == "invalid_contract"
    assert result.modelCalled is False


def test_missing_structural_field_is_rejected(valid_contract):
    valid_contract.pop("outcome")
    result = evaluate(_http(200, valid_contract))
    assert result.reason == "invalid_contract"


def test_unknown_outcome_is_invalid(valid_contract):
    valid_contract["outcome"] = "SUCCESS"
    result = evaluate(_http(200, valid_contract))
    assert result.reason == "invalid_contract"


def test_unsafe_retained_count_is_invalid(valid_contract):
    valid_contract["conditions"] = {"retainedCount": "1"}
    result = evaluate(_http(200, valid_contract))
    assert result.reason == "invalid_contract"


def test_timeout():
    result = evaluate(BoundaryResponse(kind="timeout"))
    assert result.status == "rejected"
    assert result.reason == "boundary_timeout"
    assert result.contractVersion is None
    assert result.modelCalled is False


def test_connection_error():
    result = evaluate(BoundaryResponse(kind="connection"))
    assert result.reason == "boundary_connection_error"
    assert result.modelCalled is False


def test_model_called_always_false_for_every_reason(valid_contract):
    responses = [
        _http(200, valid_contract),
        _http(200, empty_contract()),
        _http(200, empty_contract(outcome="PATIENT_CONTEXT_NOT_CONFIGURED")),
        _http(409, {"error": "conflict"}),
        _http(503, {"error": "unavailable"}),
        _http(200, text="[]"),
        BoundaryResponse(kind="timeout"),
        BoundaryResponse(kind="connection"),
    ]
    for response in responses:
        assert evaluate(response).modelCalled is False


def test_endpoint_uses_injected_settings_and_mock_transport(settings, valid_contract, monkeypatch):
    def fake_fetch(current_settings, client=None):
        assert current_settings.model_boundary_path == "/api/model-boundary/v1"
        return BoundaryResponse(kind="http", status_code=200, body_text=json.dumps(valid_contract))

    monkeypatch.setattr("app.consumer.fetch_contract", fake_fetch)
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        response = TestClient(app).get("/internal/agent-context")
        assert response.status_code == 200
        body = response.json()
        assert body == {
            "status": "received",
            "modelCalled": False,
            "contractVersion": "v1",
            "outcome": "SNAPSHOT_COMPLETE",
            "reason": None,
        }
        assert set(body.keys()) == set(RESULT_FIELDS)
    finally:
        app.dependency_overrides.clear()


def test_health():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_consume_timeout_from_httpx(settings, monkeypatch):
    def boom(self, url):
        raise httpx.TimeoutException("slow")

    monkeypatch.setattr(httpx.Client, "get", boom)
    result = consume(settings, "corr-1")
    assert result.reason == "boundary_timeout"
    assert result.modelCalled is False


def test_consume_connection_from_httpx(settings, monkeypatch):
    def boom(self, url):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(httpx.Client, "get", boom)
    result = consume(settings, "corr-2")
    assert result.reason == "boundary_connection_error"


def test_retained_count_does_not_read_records():
    payload = contract(conditions={**collection(retained_count=2), "records": []})
    result = evaluate(_http(200, payload))
    assert result.status == "received"
