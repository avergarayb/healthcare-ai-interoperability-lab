"""HTTP read client, transport, and adapter. Live reads stay opt-in.

The follow-up graph is covered by the workflow tests. This file checks the
read chain without a second graph.
"""

from __future__ import annotations

import inspect
import os

import httpx
import pytest

from app.langgraph_fhir_client import (
    CASE_IDENTIFIER_SYSTEM,
    PATIENT_CASE,
    PATIENT_ID,
    ClientFHIRTransport,
    FHIRAdapter,
    ReadClientError,
    clear_boundary_events,
)
from app.langgraph_fhir_followup import FollowUpFHIRAdapter, make_followup_tool
from app.langgraph_fhir_hapi import HapiReadClient, hapi_base_url


PATIENT_PATH = f"Patient/{PATIENT_ID}"
OBSERVATION_PATH = f"Observation?subject=Patient/{PATIENT_ID}"
SEEDED_PATIENT = {
    "resourceType": "Patient",
    "id": PATIENT_ID,
    "active": True,
    "identifier": [{"system": CASE_IDENTIFIER_SYSTEM, "value": PATIENT_CASE}],
    "name": [{"text": "Synthetic Patient"}],
}
SEEDED_OBSERVATION = {
    "resourceType": "Observation",
    "id": "obs-synthetic-001",
    "status": "final",
    "code": {"text": "Synthetic observation"},
    "subject": {"reference": f"Patient/{PATIENT_ID}"},
    "valueString": "Synthetic observation result",
}
SEEDED_BUNDLE = {
    "resourceType": "Bundle",
    "type": "searchset",
    "entry": [{"resource": SEEDED_OBSERVATION}],
}


def _hapi_enabled() -> bool:
    return os.getenv("RUN_HAPI_INTEGRATION_TESTS", "false").strip().lower() == "true"


@pytest.fixture(autouse=True)
def _clear_probe():
    clear_boundary_events()
    yield
    clear_boundary_events()


def _client(handler) -> tuple[HapiReadClient, httpx.Client]:
    http = httpx.Client(transport=httpx.MockTransport(handler), timeout=5.0)
    return HapiReadClient("http://hapi.example/fhir", http_client=http), http


def _ok(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path.endswith(f"/{PATIENT_PATH}"):
        return httpx.Response(200, json=SEEDED_PATIENT)
    if path.endswith("/Observation"):
        return httpx.Response(200, json=SEEDED_BUNDLE)
    return httpx.Response(404, json={"resourceType": "OperationOutcome"})


def test_configured_client_reads_the_seeded_patient_and_bundle():
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return _ok(request)

    client, http = _client(handler)
    try:
        patient = client.get(PATIENT_PATH)
        bundle = client.get(OBSERVATION_PATH)
    finally:
        http.close()
    assert patient["id"] == SEEDED_PATIENT["id"]
    assert patient["name"] == SEEDED_PATIENT["name"]
    observation = bundle["entry"][0]["resource"]
    assert observation["id"] == SEEDED_OBSERVATION["id"]
    assert observation["valueString"] == SEEDED_OBSERVATION["valueString"]
    assert seen[0].endswith(f"/{PATIENT_PATH}")
    assert "/Observation?" in seen[1]
    assert PATIENT_ID in seen[1]
    assert seen[0].startswith("http://hapi.example/fhir/")
    assert "obs-synthetic-001" not in inspect.getsource(HapiReadClient)
    assert "Synthetic observation result" not in inspect.getsource(HapiReadClient)


def test_transport_delegates_and_the_adapter_reads_the_observation():
    client, http = _client(_ok)
    try:
        transport = ClientFHIRTransport(client)
        adapter = FollowUpFHIRAdapter(transport)
        patient = adapter.get_patient(PATIENT_ID)
        observations = adapter.get_observations(PATIENT_ID)
    finally:
        http.close()
    assert patient["id"] == PATIENT_ID
    assert patient["name"] == "Synthetic Patient"
    assert observations[0]["id"] == SEEDED_OBSERVATION["id"]
    assert observations[0]["valueString"] == SEEDED_OBSERVATION["valueString"]
    assert transport.calls == [PATIENT_PATH, OBSERVATION_PATH]
    assert client.calls == transport.calls
    tool_source = inspect.getsource(make_followup_tool)
    for token in ("httpx", "HTTP", "FHIR_BASE_URL", "localhost"):
        assert token not in tool_source
    for owner in (FollowUpFHIRAdapter, ClientFHIRTransport, FHIRAdapter):
        assert "httpx" not in inspect.getsource(owner)
    client_source = inspect.getsource(HapiReadClient)
    assert "langgraph" not in client_source.lower()
    assert "evaluate_tool_policy" not in client_source
    assert "record_policy_audit" not in client_source


def test_base_url_comes_from_the_environment(monkeypatch):
    monkeypatch.setenv("FHIR_BASE_URL", "http://hapi.example/fhir/")
    assert hapi_base_url() == "http://hapi.example/fhir"
    assert HapiReadClient().base_url == "http://hapi.example/fhir"
    monkeypatch.setenv("FHIR_BASE_URL", "  ")
    with pytest.raises(ReadClientError, match="FHIR_BASE_URL is empty"):
        hapi_base_url()


def test_http_errors_stay_on_the_client():
    def missing(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"resourceType": "OperationOutcome", "issue": []})

    client, http = _client(missing)
    try:
        with pytest.raises(ReadClientError, match="HTTP 404"):
            client.get(PATIENT_PATH)
    finally:
        http.close()

    def broken(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"resourceType": "OperationOutcome"})

    server, server_http = _client(broken)
    try:
        with pytest.raises(ReadClientError, match="HTTP 503"):
            server.get(PATIENT_PATH)
    finally:
        server_http.close()

    def offline(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    down, down_http = _client(offline)
    try:
        with pytest.raises(ReadClientError, match="transport failed"):
            down.get(PATIENT_PATH)
    finally:
        down_http.close()


def _store(base: str, path: str, body: dict) -> None:
    response = httpx.put(
        f"{base}/{path}",
        json=body,
        headers={"Accept": "application/fhir+json", "Content-Type": "application/fhir+json"},
        timeout=5.0,
    )
    if response.status_code not in {200, 201}:
        raise AssertionError(f"seed failed with HTTP {response.status_code}")


@pytest.mark.skipif(not _hapi_enabled(), reason="set RUN_HAPI_INTEGRATION_TESTS=true to call the local server")
def test_local_server_returns_the_seeded_patient_and_observation():
    base = hapi_base_url()
    _store(base, PATIENT_PATH, SEEDED_PATIENT)
    _store(base, f"Observation/{SEEDED_OBSERVATION['id']}", SEEDED_OBSERVATION)
    client = HapiReadClient(base)
    stored_patient = client.get(PATIENT_PATH)
    stored_observation = client.get(f"Observation/{SEEDED_OBSERVATION['id']}")
    assert stored_patient["resourceType"] == "Patient"
    assert stored_patient["id"] == SEEDED_PATIENT["id"]
    assert stored_patient["name"][0]["text"] == "Synthetic Patient"
    assert stored_observation["id"] == SEEDED_OBSERVATION["id"]
    assert stored_observation["valueString"] == SEEDED_OBSERVATION["valueString"]


@pytest.mark.skipif(not _hapi_enabled(), reason="set RUN_HAPI_INTEGRATION_TESTS=true to call the local server")
def test_local_server_missing_patient_is_not_a_clinical_result():
    client = HapiReadClient(hapi_base_url())
    with pytest.raises(ReadClientError, match="HTTP 404"):
        client.get("Patient/SYN-MISSING-C16O")
