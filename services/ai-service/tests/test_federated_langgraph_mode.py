"""Opt-in federated mode. Single mode still reads Clinical Read and still pauses a match."""

from __future__ import annotations

import json
from types import SimpleNamespace

from app.clinical_federation_client import FederationClientError
from app.config import Settings
from app.human_review_client import _one_workflow
from app.langgraph_fhir_client import BoundedSearchResult, BoundedSearchStatus
from app.langgraph_workflow_orchestration import (
    GRAPH_NODES,
    LivePorts,
    SqliteCheckpointSaver,
    WorkflowReadError,
    build_live_ports,
    start_workflow,
)


POST = "post_consultation"


def _settings(**overrides) -> Settings:
    values = {
        "model_boundary_base_url": "http://interop.test",
        "model_boundary_path": "/api/model-boundary/v1",
        "model_boundary_timeout_seconds": 5,
        "model_boundary_service_token": "read-token",
        "host": "127.0.0.1",
        "port": 8090,
        "clinical_context_mode": "single",
    }
    values.update(overrides)
    return Settings(**values)


class GuardClient:
    def __init__(self) -> None:
        self.calls = 0

    def search(self, path: str, expected_resource_type: str) -> BoundedSearchResult:
        self.calls += 1
        return BoundedSearchResult(
            status=BoundedSearchStatus.COMPLETE,
            resources=({"resourceType": "Patient", "id": "syn-demo-patient-102"},),
        )

    def get(self, path: str) -> dict:
        self.calls += 1
        raise AssertionError(path)


class FederationDouble:
    def __init__(self, payload=None, error: str | None = None) -> None:
        self.payload = payload
        self.error = error
        self.calls = 0

    def query(self, identifier_value: str) -> dict:
        self.calls += 1
        assert identifier_value == "MHS-PAT-001"
        if self.error:
            raise FederationClientError(self.error)
        return self.payload


def _envelope(status: str, sources: list[dict], entries: list[dict]) -> dict:
    return {
        "contractVersion": "clinical-federation-v1",
        "status": status,
        "correlationId": "FED-UNIT-GRAPH00001",
        "callerSystem": "mini-his",
        "sources": sources,
        "entries": entries,
    }


def _entry(source: str, resource: dict) -> dict:
    return {
        "sourceKey": source,
        "fullUrl": f"http://127.0.0.1/{source}/{resource['resourceType']}/{resource['id']}",
        "resource": resource,
    }


def _patient() -> dict:
    return {
        "resourceType": "Patient",
        "id": "MHS-PAT-001",
        "meta": {"source": "https://lab.local/mini-his"},
        "identifier": [{"system": "https://lab.local/mini-his/patient", "value": "MHS-PAT-001"}],
        "name": [{"family": "Quispe"}],
    }


def _observation(source: str, observation_id: str, value: float) -> dict:
    return {
        "resourceType": "Observation",
        "id": observation_id,
        "status": "final",
        "effectiveDateTime": "2026-03-01T12:00:00Z",
        "meta": {"source": f"https://lab.local/{source}"},
        "valueQuantity": {"value": value, "unit": "mmol/L" if source == "mini-lis" else "g/dL"},
        "identifier": [{"system": f"https://lab.local/{source}/observation", "value": observation_id}],
    }


def _ports(tmp_path, federation: FederationDouble) -> tuple[LivePorts, GuardClient]:
    client = GuardClient()
    ports = LivePorts(_settings(clinical_context_mode="federated"), object(), client, federation)
    return ports, client


def _run(tmp_path, ports: LivePorts) -> dict:
    saver = SqliteCheckpointSaver(tmp_path / "agent-workflow.sqlite3")
    return start_workflow(saver, ports, "MHS-PAT-001", POST)


def test_single_mode_reads_clinical_read_and_does_not_construct_federation(tmp_path):
    del tmp_path
    ports = build_live_ports(_settings(), object())
    client = GuardClient()
    ports.client = client
    assert ports.federation is None
    assert ports.read_patient("SYN-FOLLOWUP-001", POST) == "Patient/syn-demo-patient-102"
    assert client.calls == 1


def test_federated_factory_keeps_clinical_read_client_and_adds_federation():
    ports = build_live_ports(
        _settings(
            clinical_context_mode="federated",
            federation_participant_token="participant-token",
            federation_requesting_organization_id="org-mini-his",
            federation_patient_system_key="mini-his",
            federation_patient_identifier_system="https://lab.local/mini-his/patient",
            federation_sources=("mini-his", "mini-lis"),
        ),
        object(),
    )
    assert type(ports.client).__name__ == "ClinicalReadClient"
    assert type(ports.federation).__name__ == "ClinicalFederationClient"
    assert ports.federation.sources == ("mini-his", "mini-lis")


def test_complete_federated_context_does_not_invent_a_protocol_match(tmp_path):
    federation = FederationDouble(
        _envelope(
            "complete",
            [
                {"sourceKey": "mini-his", "organizationId": "org-mini-his", "outcome": "complete", "resourceCount": 2},
                {"sourceKey": "mini-lis", "organizationId": "org-mini-lis", "outcome": "complete", "resourceCount": 2},
            ],
            [
                _entry("mini-his", _patient()),
                _entry("mini-lis", _observation("mini-lis", "MLS-OBS-001", 141)),
                _entry("mini-his", _observation("mini-his", "MHS-OBS-001", 13.4)),
            ],
        )
    )
    ports, client = _ports(tmp_path, federation)
    view = _run(tmp_path, ports)
    assert client.calls == 0
    assert federation.calls == 1
    assert view["status"] == "completed"
    assert view["protocol"]["evaluationStatus"] == "insufficient"
    assert view["protocol"]["reasonCodes"] == ["federated_protocol_not_resolved"]
    assert "human_review" not in view["steps"]
    assert "human_review" in GRAPH_NODES
    federation_view = view["clinicalContext"]["federation"]
    assert federation_view["status"] == "complete"
    assert {item["outcome"] for item in federation_view["sources"]} == {"complete"}
    observations = [item for item in federation_view["resources"] if item["resourceType"] == "Observation"]
    assert {item["source"] for item in observations} == {"https://lab.local/mini-his", "https://lab.local/mini-lis"}
    rendered = json.dumps(view)
    assert "Quispe" not in rendered
    assert "13.4" not in rendered
    assert "141" not in rendered


def test_partial_context_stays_visible_and_is_not_a_complete_review(tmp_path):
    federation = FederationDouble(
        _envelope(
            "partial",
            [
                {"sourceKey": "mini-his", "organizationId": "org-mini-his", "outcome": "complete", "resourceCount": 1},
                {"sourceKey": "mini-lis", "organizationId": "org-mini-lis", "outcome": "identity_unresolved", "resourceCount": 0},
            ],
            [_entry("mini-his", _patient())],
        )
    )
    ports, client = _ports(tmp_path, federation)
    view = _run(tmp_path, ports)
    assert client.calls == 0
    assert view["status"] == "completed"
    assert view["clinicalContext"]["contextStatus"] == "partial"
    assert "federated_context_partial" in view["protocol"]["reasonCodes"]
    html = _one_workflow(SimpleNamespace(narrative_text=None), view)
    assert "Esta lectura no es una revisión clínica completa." in html
    assert "identity_unresolved:mini-lis" in html
    assert "mini-lis" in html


def test_failed_federation_does_not_look_like_a_valid_evaluation(tmp_path):
    federation = FederationDouble(
        _envelope(
            "failed",
            [
                {"sourceKey": "mini-his", "organizationId": "org-mini-his", "outcome": "unavailable", "resourceCount": 0, "error": "timeout"},
                {"sourceKey": "mini-lis", "organizationId": "org-mini-lis", "outcome": "unavailable", "resourceCount": 0, "error": "source_error"},
            ],
            [],
        )
    )
    ports, client = _ports(tmp_path, federation)
    view = _run(tmp_path, ports)
    assert client.calls == 0
    assert view["status"] == "failed"
    assert view["errorCode"] == "federation_failed"
    assert view["protocol"]["evaluationStatus"] == "unavailable"
    assert view["clinicalContext"]["federation"]["resources"] == []
    assert "federation_failed" in view["clinicalContext"]["federation"]["warnings"]


def test_denied_federation_does_not_fall_back_to_clinical_read(tmp_path):
    federation = FederationDouble(error="federation_unauthorized")
    ports, client = _ports(tmp_path, federation)
    view = _run(tmp_path, ports)
    assert client.calls == 0
    assert view["status"] == "failed"
    assert view["errorCode"] == "federation_unauthorized"
    assert view["clinicalContext"]["federation"]["warnings"] == ["federation_unauthorized"]


def test_read_error_code_is_stable():
    error = WorkflowReadError("federation_timeout")
    assert error.code == "federation_timeout"


class MatchedPorts:
    def read_patient(self, case_id: str, workflow_type: str) -> str:
        del case_id, workflow_type
        return "Patient/syn-demo-patient-102"

    def build_context(self, case_id: str) -> dict:
        del case_id
        return {
            "context": {
                "schema": "LONGITUDINAL_CONTEXT_V1",
                "contextStatus": "partial",
                "federation": {
                    "status": "partial",
                    "sources": [{"sourceKey": "mini-lis", "outcome": "identity_unresolved"}],
                    "warnings": ["federation_partial"],
                    "resources": [],
                    "reports": [],
                },
            },
            "intelligence": {"schema": "CLINICAL_CONTEXT_INTELLIGENCE_V1", "contextStatus": "partial"},
        }

    def evaluate(self, case_id: str, workflow_type: str) -> dict:
        del case_id, workflow_type
        return {
            "protocolId": "POST_CONSULTATION_RESULT_REVIEW_V1",
            "evaluationStatus": "matched",
            "reasonCodes": ["post_consultation_result_requires_review", "federated_context_partial"],
            "evidence": ["Observation/MHS-OBS-001"],
        }

    def prepare_narrative(self, state: dict) -> str:
        del state
        return "unavailable"

    def ensure_review(self, state: dict) -> str:
        return f"review-{state['case_id']}"

    def store_prepared_narrative(self, review_case_id: str, state: dict) -> None:
        del review_case_id, state


def test_matched_protocol_still_reaches_human_review(tmp_path):
    saver = SqliteCheckpointSaver(tmp_path / "agent-workflow.sqlite3")
    view = start_workflow(saver, MatchedPorts(), "SYN-FOLLOWUP-001", POST)
    assert view["status"] == "waiting_human"
    assert view["currentStep"] == "await_human"
    assert "human_review" in view["steps"]
    assert "human_review" in GRAPH_NODES
    html = _one_workflow(SimpleNamespace(narrative_text=None), view)
    assert "Esta lectura no es una revisión clínica completa." in html
    assert "federated_context_partial" in html

