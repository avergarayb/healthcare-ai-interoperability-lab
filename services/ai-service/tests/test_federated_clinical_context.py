"""Federation envelope adaptation. Same code and value stay separate resources."""

from __future__ import annotations

import json

from app.federated_clinical_context import adapt_federation_envelope, failure_projection


def _patient(source: str, patient_id: str) -> dict:
    return {
        "sourceKey": source,
        "fullUrl": f"http://127.0.0.1/{source}/Patient/{patient_id}",
        "resource": {
            "resourceType": "Patient",
            "id": patient_id,
            "meta": {"source": f"https://lab.local/{source}"},
            "identifier": [{"system": "https://lab.local/mini-his/patient", "value": "MHS-PAT-001"}],
            "name": [{"family": "Quispe", "given": ["Ana"]}],
        },
    }


def _observation(source: str, observation_id: str, value: float, unit: str) -> dict:
    return {
        "sourceKey": source,
        "fullUrl": f"http://127.0.0.1/{source}/Observation/{observation_id}",
        "resource": {
            "resourceType": "Observation",
            "id": observation_id,
            "status": "final",
            "effectiveDateTime": "2026-03-01T12:00:00Z",
            "meta": {"source": f"https://lab.local/{source}"},
            "code": {"coding": [{"system": "http://loinc.org", "code": "718-7"}]},
            "valueQuantity": {"value": value, "unit": unit},
            "identifier": [{"system": f"https://lab.local/{source}/observation", "value": observation_id}],
        },
    }


def _source(source: str, outcome: str, count: int, error: str | None = None) -> dict:
    return {
        "sourceKey": source,
        "organizationId": f"org-{source}",
        "outcome": outcome,
        "resourceCount": count,
        "error": error,
    }


def _envelope(status: str, sources: list[dict], entries: list[dict]) -> dict:
    return {
        "contractVersion": "clinical-federation-v1",
        "status": status,
        "correlationId": "FED-UNIT-ADAPT00001",
        "callerSystem": "mini-his",
        "truncated": False,
        "sources": sources,
        "entries": entries,
    }


def test_complete_context_keeps_both_sources_and_does_not_merge_values():
    envelope = _envelope(
        "complete",
        [_source("mini-his", "complete", 2), _source("mini-lis", "complete", 2)],
        [
            _patient("mini-his", "MHS-PAT-001"),
            _patient("mini-lis", "MLS-PAT-001"),
            _observation("mini-his", "MHS-OBS-001", 13.4, "g/dL"),
            _observation("mini-lis", "MLS-OBS-001", 13.4, "g/dL"),
        ],
    )
    context, projection = adapt_federation_envelope(envelope, "MHS-PAT-001")
    assert context.status == "complete"
    assert context.patient_id == "MHS-PAT-001"
    assert len(context.observations) == 2
    assert {item.source for item in context.observations} == {
        "https://lab.local/mini-his",
        "https://lab.local/mini-lis",
    }
    assert {item.recorded_value for item in context.observations} == {"13.4 g/dL"}
    rendered = json.dumps(projection)
    assert "Quispe" not in rendered
    assert "13.4" not in rendered
    assert {item["sourceKey"] for item in projection["resources"] if item["resourceType"] == "Observation"} == {
        "mini-his",
        "mini-lis",
    }


def test_same_fhir_id_from_two_sources_stays_two_references():
    envelope = _envelope(
        "complete",
        [_source("mini-his", "complete", 1), _source("mini-lis", "complete", 1)],
        [
            _observation("mini-his", "OBS-1", 13.4, "g/dL"),
            _observation("mini-lis", "OBS-1", 141, "mmol/L"),
        ],
    )
    context, projection = adapt_federation_envelope(envelope, "MHS-PAT-001")
    assert {item.reference for item in context.observations} == {"Observation/OBS-1", "Observation/mini-lis~OBS-1"}
    assert len(projection["resources"]) == 2


def test_partial_identity_miss_is_not_a_complete_review():
    envelope = _envelope(
        "partial",
        [
            _source("mini-his", "complete", 1),
            _source("mini-lis", "identity_unresolved", 0),
        ],
        [_patient("mini-his", "MHS-PAT-001"), _observation("mini-his", "MHS-OBS-001", 13.4, "g/dL")],
    )
    context, projection = adapt_federation_envelope(envelope, "MHS-PAT-001")
    assert context.status == "partial"
    assert projection["status"] == "partial"
    assert "federation_partial" in projection["warnings"]
    assert "identity_unresolved:mini-lis" in projection["warnings"]
    assert len(context.observations) == 1


def test_empty_authorized_source_is_not_an_identity_miss():
    envelope = _envelope(
        "complete",
        [_source("mini-his", "complete", 1), _source("mini-lis", "complete", 0)],
        [_patient("mini-his", "MHS-PAT-001")],
    )
    context, projection = adapt_federation_envelope(envelope, "MHS-PAT-001")
    assert context.status == "complete"
    assert "no_resources:mini-lis" in projection["warnings"]
    assert not any(item.startswith("identity_unresolved") for item in projection["warnings"])


def test_failed_envelope_is_unavailable_and_has_no_clinical_entries():
    envelope = _envelope(
        "failed",
        [
            _source("mini-his", "unavailable", 0, "timeout"),
            _source("mini-lis", "unavailable", 0, "source_error"),
        ],
        [_observation("mini-his", "MHS-OBS-001", 13.4, "g/dL")],
    )
    context, projection = adapt_federation_envelope(envelope, "MHS-PAT-001")
    assert context.status == "unavailable"
    assert context.observations == []
    assert projection["resources"] == []
    assert "federation_failed" in projection["warnings"]
    assert "unavailable:mini-his" in projection["warnings"]


def test_access_denial_projection_has_no_chart():
    projected = failure_projection("federation_unauthorized")
    assert projected["contextStatus"] == "unavailable"
    assert projected["federation"]["resources"] == []
    assert projected["federation"]["warnings"] == ["federation_unauthorized"]
