"""Clinical Federation client. Responses are envelopes, not FHIR Bundles."""

from __future__ import annotations

import json

import httpx
import pytest

from app.clinical_federation_client import (
    CONTRACT_VERSION,
    ClinicalFederationClient,
    FederationClientError,
)
from app.config import Settings


def _client(http_client: httpx.Client | None = None, **overrides) -> ClinicalFederationClient:
    values = {
        "base_url": "http://interop.test",
        "service_token": "participant-token",
        "organization_id": "org-mini-his",
        "patient_system_key": "mini-his",
        "patient_identifier_system": "https://lab.local/mini-his/patient",
        "sources": ("mini-his", "mini-lis"),
        "timeout_seconds": 5,
        "http_client": http_client,
    }
    values.update(overrides)
    return ClinicalFederationClient(**values)


def _envelope(status: str = "complete") -> dict:
    return {
        "contractVersion": CONTRACT_VERSION,
        "status": status,
        "correlationId": "FED-UNIT-CLIENT0001",
        "callerSystem": "mini-his",
        "sources": [
            {"sourceKey": "mini-his", "outcome": "complete", "resourceCount": 1},
        ],
        "entries": [],
    }


def _transport(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_query_sends_only_configured_identity_and_sources():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["token"] = request.headers["X-Service-Token"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=_envelope())

    parsed = _client(_transport(handler)).query("MHS-PAT-001")
    body = seen["body"]
    assert seen["url"] == "http://interop.test/api/clinical-federation/v1/context"
    assert seen["token"] == "participant-token"
    assert body["requestingOrganizationId"] == "org-mini-his"
    assert body["patient"] == {
        "systemKey": "mini-his",
        "identifierSystem": "https://lab.local/mini-his/patient",
        "identifierValue": "MHS-PAT-001",
    }
    assert body["sources"] == ["mini-his", "mini-lis"]
    assert "Patient" in body["resourceTypes"]
    assert "DiagnosticReport" in body["resourceTypes"]
    assert "familyName" not in body["patient"]
    assert "name" not in body["patient"]
    assert parsed["status"] == "complete"


def test_invalid_identity_does_not_call_java():
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(request.url)

    with pytest.raises(FederationClientError) as caught:
        _client(_transport(handler)).query("not a patient")
    assert caught.value.code == "federation_invalid_identity"


@pytest.mark.parametrize(
    ("status", "code"),
    [(401, "federation_unauthenticated"), (403, "federation_unauthorized"), (400, "federation_rejected")],
)
def test_auth_and_rejection_codes(status: int, code: str):
    client = _client(_transport(lambda request: httpx.Response(status)))
    with pytest.raises(FederationClientError) as caught:
        client.query("MHS-PAT-001")
    assert caught.value.code == code
    assert "MHS-PAT-001" not in str(caught.value)


def test_timeout_is_a_stable_code():
    class Slow:
        def post(self, *args, **kwargs):
            raise httpx.ReadTimeout("slow")

    with pytest.raises(FederationClientError) as caught:
        _client(Slow()).query("MHS-PAT-001")
    assert caught.value.code == "federation_timeout"


def test_bundle_shaped_body_is_rejected():
    body = {"resourceType": "Bundle", "type": "searchset", "entry": []}
    client = _client(_transport(lambda request: httpx.Response(200, json=body)))
    with pytest.raises(FederationClientError) as caught:
        client.query("MHS-PAT-001")
    assert caught.value.code == "federation_unavailable"


def test_blank_token_fails_closed():
    with pytest.raises(FederationClientError) as caught:
        _client(service_token=" ")
    assert caught.value.code == "federation_unconfigured"


def test_from_env_defaults_to_single_and_federated_requires_a_known_mode(monkeypatch):
    monkeypatch.delenv("AI_CLINICAL_CONTEXT_MODE", raising=False)
    assert Settings.from_env().clinical_context_mode == "single"
    monkeypatch.setenv("AI_CLINICAL_CONTEXT_MODE", "both")
    with pytest.raises(ValueError, match="AI_CLINICAL_CONTEXT_MODE"):
        Settings.from_env()
