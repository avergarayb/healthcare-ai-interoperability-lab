"""Clinical Read API v1 client and the missed follow-up wiring."""

from __future__ import annotations

import inspect
from datetime import datetime, timezone
from urllib.parse import parse_qs, quote, urlsplit

import httpx

from app.clinical_read_client import ClinicalReadClient
from app.config import Settings
from app.langgraph_fhir_client import (
    CASE_IDENTIFIER_SYSTEM,
    BoundedSearchStatus,
    ClientFHIRTransport,
    ExactResourceNotFound,
)
from app.langgraph_fhir_followup import (
    FollowUpFHIRAdapter,
    case_resolution_search_path,
    encounter_search_path,
    patient_resource_path,
    protocol_appointment_search_path,
    protocol_observation_search_path,
)
from app.langgraph_followup_workflow import build_live_followup_workflow
from app.missed_follow_up_review import REASON_MISSED
from app.missed_follow_up_service import _live_adapter, evaluate_missed_follow_up_case
from app.post_consultation_review import ProtocolEvaluationStatus


TOKEN = "test-model-boundary-token"
PATIENT_ID = "syn-demo-patient-102"
CASE_ID = "SYN-DEMO-102"
APPOINTMENT_ID = "syn-demo-noshow-102"
INSTANT = datetime(2026, 9, 29, tzinfo=timezone.utc)


def _settings() -> Settings:
    return Settings(
        model_boundary_base_url="http://interop.test",
        model_boundary_path="/api/model-boundary/v1",
        model_boundary_timeout_seconds=5,
        model_boundary_service_token=TOKEN,
        host="127.0.0.1",
        port=8090,
    )


def _patient() -> dict:
    return {
        "resourceType": "Patient",
        "id": PATIENT_ID,
        "identifier": [{"system": CASE_IDENTIFIER_SYSTEM, "value": CASE_ID}],
        "name": [{"text": "Synthetic demo patient 102"}],
    }


def _appointment() -> dict:
    return {
        "resourceType": "Appointment",
        "id": APPOINTMENT_ID,
        "status": "noshow",
        "start": "2026-01-01T00:00:00Z",
        "end": "2026-01-01T00:30:00Z",
        "participant": [{"actor": {"reference": f"Patient/{PATIENT_ID}"}, "status": "accepted"}],
    }


def _search(resource_type: str, resources: list[dict], collection_status: str = "complete") -> dict:
    return {
        "contractVersion": "clinical-read-v1",
        "destination": "local-hapi",
        "collectionStatus": collection_status,
        "resourceType": resource_type,
        "resources": resources,
    }


def _read(resource: dict) -> dict:
    return {"contractVersion": "clinical-read-v1", "destination": "local-hapi", "resource": resource}


def _client(handler) -> tuple[ClinicalReadClient, httpx.Client]:
    http = httpx.Client(transport=httpx.MockTransport(handler), timeout=5.0)
    return ClinicalReadClient.from_settings(_settings(), http_client=http), http


def test_patient_search_read_and_appointment_keep_clinical_fields():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        assert request.headers["X-Service-Token"] == TOKEN
        path = request.url.path
        if path.endswith("/patients") and "identifierSystem" in request.url.params:
            assert request.url.params["identifierSystem"] == CASE_IDENTIFIER_SYSTEM
            assert request.url.params["identifierValue"] == CASE_ID
            return httpx.Response(200, json=_search("Patient", [_patient()]))
        if path.endswith(f"/patients/{PATIENT_ID}"):
            return httpx.Response(200, json=_read(_patient()))
        if path.endswith("/appointments"):
            assert request.url.params["patient"] == PATIENT_ID
            return httpx.Response(200, json=_search("Appointment", [_appointment()]))
        raise AssertionError(path)

    client, http = _client(handler)
    try:
        found = client.search(case_resolution_search_path(CASE_ID), "Patient")
        patient = client.get(patient_resource_path(PATIENT_ID))
        appointments = client.search(protocol_appointment_search_path(PATIENT_ID), "Appointment")
    finally:
        http.close()

    assert found.status is BoundedSearchStatus.COMPLETE
    assert found.resources[0]["id"] == PATIENT_ID
    assert found.resources[0]["identifier"] == [{"system": CASE_IDENTIFIER_SYSTEM, "value": CASE_ID}]
    assert patient["id"] == PATIENT_ID
    assert patient["name"] == [{"text": "Synthetic demo patient 102"}]
    assert appointments.status is BoundedSearchStatus.COMPLETE
    assert appointments.resources[0]["status"] == "noshow"
    assert appointments.resources[0]["start"] == "2026-01-01T00:00:00Z"
    assert appointments.resources[0]["participant"][0]["actor"]["reference"] == f"Patient/{PATIENT_ID}"
    assert all(item.url.host == "interop.test" for item in seen)
    assert all("/api/clinical-read/v1/" in str(item.url) for item in seen)


def test_reserved_characters_in_the_identifier_system_stay_in_one_parameter():
    system = "https://lab.example/sys?a=1&b=2"

    def handler(request: httpx.Request) -> httpx.Response:
        raw = urlsplit(str(request.url)).query
        parsed = parse_qs(raw, keep_blank_values=True)
        assert parsed["identifierSystem"] == [system]
        assert parsed["identifierValue"] == ["CASE 100"]
        assert "%5C%7C" not in raw
        return httpx.Response(200, json=_search("Patient", []))

    client, http = _client(handler)
    token = quote(f"{system}|CASE 100", safe="")
    try:
        result = client.search(f"Patient?identifier={token}&_count=2", "Patient")
    finally:
        http.close()
    assert result.status is BoundedSearchStatus.COMPLETE
    assert result.resources == ()


def test_incomplete_unavailable_and_not_found_stay_distinct():
    def handler(request: httpx.Request) -> httpx.Response:
        value = request.url.params.get("identifierValue")
        if value == "incomplete":
            return httpx.Response(200, json=_search("Patient", [_patient()], "incomplete"))
        if value == "down":
            return httpx.Response(503, json={"error": "unavailable"})
        if value == "missing-search":
            return httpx.Response(404, json={"error": "not_found"})
        if request.url.path.endswith("/patients/missing-patient"):
            return httpx.Response(404, json={"error": "not_found"})
        if request.url.path.endswith("/patients/broken"):
            return httpx.Response(503, json={"error": "unavailable"})
        if request.headers.get("X-Service-Token") == "wrong":
            return httpx.Response(401)
        raise AssertionError(str(request.url))

    client, http = _client(handler)
    try:
        incomplete = client.search(
            f"Patient?identifier={quote('https://lab.local/id|incomplete', safe='')}&_count=2",
            "Patient",
        )
        unavailable = client.search(
            f"Patient?identifier={quote('https://lab.local/id|down', safe='')}&_count=2",
            "Patient",
        )
        search_not_found = client.search(
            f"Patient?identifier={quote('https://lab.local/id|missing-search', safe='')}&_count=2",
            "Patient",
        )
        try:
            client.get("Patient/missing-patient")
        except ExactResourceNotFound:
            missing = "not_found"
        else:
            missing = "returned"
        try:
            client.get("Patient/broken")
        except ExactResourceNotFound:
            broken = "not_found"
        except Exception as exc:
            broken = type(exc).__name__
        else:
            broken = "returned"
        rejected = ClinicalReadClient(
            "http://interop.test",
            "wrong",
            http_client=http,
        ).search(
            f"Patient?identifier={quote('https://lab.local/id|CASE', safe='')}&_count=2",
            "Patient",
        )
    finally:
        http.close()

    assert incomplete.status is BoundedSearchStatus.INCOMPLETE_LIMIT
    assert incomplete.resources[0]["id"] == PATIENT_ID
    assert unavailable.status is BoundedSearchStatus.FAILED
    assert unavailable.resources == ()
    assert search_not_found.status is BoundedSearchStatus.FAILED
    assert search_not_found.resources == ()
    assert missing == "not_found"
    assert broken == "ReadClientError"
    assert rejected.status is BoundedSearchStatus.FAILED
    assert rejected.resources == ()


def test_blank_token_and_connection_failure_do_not_become_an_empty_collection():
    def handler(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("blank token must not call Java")

    silent, http = _client(handler)
    blank = ClinicalReadClient("http://interop.test", "  ", http_client=http)
    try:
        result = blank.search(case_resolution_search_path(CASE_ID), "Patient")
    finally:
        http.close()
    assert result.status is BoundedSearchStatus.FAILED
    assert result.resources == ()

    def fail(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    failing, failing_http = _client(fail)
    try:
        down = failing.search(protocol_appointment_search_path(PATIENT_ID), "Appointment")
    finally:
        failing_http.close()
    assert down.status is BoundedSearchStatus.FAILED
    assert down.resources == ()
    assert silent.base_url == "http://interop.test"


def test_migrated_protocol_matches_a_past_noshow_and_keeps_hapi_for_post_consultation():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith(f"/patients/{PATIENT_ID}"):
            return httpx.Response(200, json=_read(_patient()))
        if request.url.path.endswith("/appointments"):
            return httpx.Response(200, json=_search("Appointment", [_appointment()]))
        if request.url.path.endswith("/patients"):
            return httpx.Response(200, json=_search("Patient", [_patient()]))
        raise AssertionError(request.url.path)

    client, http = _client(handler)
    try:
        evaluation = evaluate_missed_follow_up_case(
            FollowUpFHIRAdapter(ClientFHIRTransport(client), now=lambda: INSTANT),
            CASE_ID,
            INSTANT,
        )
    finally:
        http.close()
    assert evaluation.status is ProtocolEvaluationStatus.MATCHED
    assert evaluation.reason_codes == (REASON_MISSED,)
    assert evaluation.provenance_resources == (f"Appointment/{APPOINTMENT_ID}",)
    assert evaluation.triggers == (f"Appointment/{APPOINTMENT_ID}",)

    def incomplete(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/appointments"):
            return httpx.Response(200, json=_search("Appointment", [_appointment()], "incomplete"))
        if request.url.path.endswith(f"/patients/{PATIENT_ID}"):
            return httpx.Response(200, json=_read(_patient()))
        return httpx.Response(200, json=_search("Patient", [_patient()]))

    partial, partial_http = _client(incomplete)
    try:
        partial_result = evaluate_missed_follow_up_case(
            FollowUpFHIRAdapter(ClientFHIRTransport(partial), now=lambda: INSTANT),
            CASE_ID,
            INSTANT,
        )
    finally:
        partial_http.close()
    assert partial_result.status is ProtocolEvaluationStatus.INSUFFICIENT
    assert partial_result.reason_codes == ("appointment_search_incomplete",)
    assert partial_result.triggers == ()

    def down(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "unavailable"})

    offline, offline_http = _client(down)
    try:
        offline_result = evaluate_missed_follow_up_case(
            FollowUpFHIRAdapter(ClientFHIRTransport(offline), now=lambda: INSTANT),
            CASE_ID,
            INSTANT,
        )
    finally:
        offline_http.close()
    assert offline_result.status is ProtocolEvaluationStatus.UNAVAILABLE
    assert offline_result.reason_codes == ("patient_resolution_unavailable",)
    assert offline_result.triggers == ()

    missed_source = inspect.getsource(_live_adapter)
    workflow_source = inspect.getsource(build_live_followup_workflow)
    assert "ClinicalReadClient" in missed_source
    assert "HapiReadClient" not in missed_source
    assert "HapiReadClient" in workflow_source


def test_encounter_and_observation_reads_keep_fields_and_java_errors():
    encounter = {
        "resourceType": "Encounter",
        "id": "MHS-CON-001",
        "status": "finished",
        "class": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "AMB"},
        "subject": {"reference": f"Patient/{PATIENT_ID}"},
        "period": {"start": "2026-09-01T15:00:00Z"},
    }
    observation = {
        "resourceType": "Observation",
        "id": "MHS-RES-001",
        "status": "final",
        "subject": {"reference": f"Patient/{PATIENT_ID}"},
        "encounter": {"reference": "Encounter/MHS-CON-001"},
        "effectiveDateTime": "2026-09-01T15:10:00Z",
        "valueQuantity": {"value": 13.4, "unit": "g/dL"},
    }
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(f"{request.method} {request.url}")
        if request.headers.get("X-Service-Token") != TOKEN:
            return httpx.Response(401)
        assert request.url.host == "interop.test"
        assert request.url.path.startswith("/api/clinical-read/v1/")
        assert "8080" not in str(request.url)
        path = request.url.path
        if path.endswith("/encounters") and request.url.params.get("status") == "finished":
            assert request.url.params["patient"] == PATIENT_ID
            assert "_count" not in request.url.params
            return httpx.Response(200, json=_search("Encounter", [encounter]))
        if path.endswith("/encounters") and request.url.params.get("status") == "incomplete":
            return httpx.Response(200, json=_search("Encounter", [encounter], "incomplete"))
        if path.endswith("/encounters/MHS-CON-001"):
            return httpx.Response(200, json=_read(encounter))
        if path.endswith("/observations") and request.url.params.get("status") == "final":
            assert request.url.params["patient"] == PATIENT_ID
            return httpx.Response(200, json=_search("Observation", [observation]))
        if path.endswith("/observations") and request.url.params.get("status") == "partial":
            return httpx.Response(200, json=_search("Observation", [observation], "incomplete"))
        if path.endswith("/observations/MHS-RES-001"):
            return httpx.Response(200, json=_read(observation))
        if path.endswith("/encounters/missing"):
            return httpx.Response(404, json={"error": "not_found"})
        if path.endswith("/observations/missing"):
            return httpx.Response(404, json={"error": "not_found"})
        if path.endswith("/observations/unsupported"):
            return httpx.Response(409, json={"error": "operation_not_supported"})
        if path.endswith("/observations/invalid"):
            return httpx.Response(422, json={"error": "invalid_source"})
        if path.endswith("/observations/down"):
            return httpx.Response(503, json={"error": "unavailable"})
        if path.endswith("/encounters") and request.url.params.get("status") == "blocked":
            return httpx.Response(409, json={"error": "operation_not_supported"})
        if path.endswith("/observations") and request.url.params.get("status") == "invalid":
            return httpx.Response(422, json={"error": "invalid_source"})
        if path.endswith("/observations") and request.url.params.get("status") == "down":
            return httpx.Response(503, json={"error": "unavailable"})
        raise AssertionError(str(request.url))

    client, http = _client(handler)
    try:
        encounters = client.search(encounter_search_path(PATIENT_ID), "Encounter")
        one_encounter = client.get("Encounter/MHS-CON-001")
        observations = client.search(protocol_observation_search_path(PATIENT_ID), "Observation")
        one_observation = client.get("Observation/MHS-RES-001")
        incomplete_encounters = client.search(
            f"Encounter?patient=Patient/{PATIENT_ID}&status=incomplete&_count=25",
            "Encounter",
        )
        incomplete_observations = client.search(
            f"Observation?subject=Patient/{PATIENT_ID}&status=partial&_count=25",
            "Observation",
        )
        try:
            client.get("Encounter/missing")
        except ExactResourceNotFound:
            missing_encounter = "not_found"
        else:
            missing_encounter = "returned"
        try:
            client.get("Observation/missing")
        except ExactResourceNotFound:
            missing_observation = "not_found"
        else:
            missing_observation = "returned"
        exact_errors = {}
        for logical_id, label in (
            ("unsupported", "conflict"),
            ("invalid", "invalid_source"),
            ("down", "unavailable"),
        ):
            try:
                client.get(f"Observation/{logical_id}")
            except ExactResourceNotFound:
                exact_errors[label] = "not_found"
            except Exception as exc:
                exact_errors[label] = type(exc).__name__
            else:
                exact_errors[label] = "returned"
        blocked = client.search(
            f"Encounter?patient=Patient/{PATIENT_ID}&status=blocked",
            "Encounter",
        )
        denied = ClinicalReadClient("http://interop.test", "wrong", http_client=http).search(
            f"Observation?patient=Patient/{PATIENT_ID}&status=denied",
            "Observation",
        )
        invalid_search = client.search(
            f"Observation?subject=Patient/{PATIENT_ID}&status=invalid",
            "Observation",
        )
        unavailable = client.search(
            f"Observation?patient={PATIENT_ID}&status=down",
            "Observation",
        )
    finally:
        http.close()

    assert encounters.status is BoundedSearchStatus.COMPLETE
    assert encounters.resources[0]["status"] == "finished"
    assert encounters.resources[0]["class"]["code"] == "AMB"
    assert encounters.resources[0]["subject"]["reference"] == f"Patient/{PATIENT_ID}"
    assert encounters.resources[0]["period"]["start"] == "2026-09-01T15:00:00Z"
    assert one_encounter["id"] == "MHS-CON-001"
    assert observations.status is BoundedSearchStatus.COMPLETE
    assert observations.resources[0]["status"] == "final"
    assert observations.resources[0]["encounter"]["reference"] == "Encounter/MHS-CON-001"
    assert observations.resources[0]["effectiveDateTime"] == "2026-09-01T15:10:00Z"
    assert observations.resources[0]["valueQuantity"]["value"] == 13.4
    assert one_observation["subject"]["reference"] == f"Patient/{PATIENT_ID}"
    assert incomplete_encounters.status is BoundedSearchStatus.INCOMPLETE_LIMIT
    assert incomplete_observations.status is BoundedSearchStatus.INCOMPLETE_LIMIT
    assert incomplete_observations.resources[0]["id"] == "MHS-RES-001"
    assert missing_encounter == "not_found"
    assert missing_observation == "not_found"
    assert exact_errors == {
        "conflict": "ReadClientError",
        "invalid_source": "ReadClientError",
        "unavailable": "ReadClientError",
    }
    assert blocked.status is BoundedSearchStatus.FAILED
    assert blocked.resources == ()
    assert denied.status is BoundedSearchStatus.FAILED
    assert denied.resources == ()
    assert invalid_search.status is BoundedSearchStatus.FAILED
    assert invalid_search.resources == ()
    assert unavailable.status is BoundedSearchStatus.FAILED
    assert unavailable.resources == ()
    assert all("/api/clinical-read/v1/" in item for item in seen)
    client_source = inspect.getsource(ClinicalReadClient)
    assert "HapiReadClient" not in client_source
    assert "8080" not in client_source
    assert "HapiReadClient" in inspect.getsource(build_live_followup_workflow)
