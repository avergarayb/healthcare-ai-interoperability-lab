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
    assert "finished_encounter_missing" in view["protocol"]["reasonCodes"]
    assert "human_review" not in view["steps"]
    assert "human_review" in GRAPH_NODES
    federation_view = view["clinicalContext"]["federation"]
    assert federation_view["status"] == "complete"
    assert {item["outcome"] for item in federation_view["sources"]} == {"complete"}
    observations = [item for item in federation_view["resources"] if item["resourceType"] == "Observation"]
    assert {item["source"] for item in observations} == {"https://lab.local/mini-his", "https://lab.local/mini-lis"}
    rendered = json.dumps(view)
    assert "Quispe" not in rendered
    assert "13.4" in rendered
    assert "141" in rendered


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


def test_structural_pair_reaches_human_review_without_clinical_read(tmp_path):
    from app.followup_review import FollowUpReviewCaseService
    from app.followup_review_sqlite import SQLiteFollowUpReviewCaseRepository
    from app.human_review_client import _one_workflow

    repository = SQLiteFollowUpReviewCaseRepository(tmp_path / "review.sqlite3")
    repository.initialize()
    encounter = {
        "resourceType": "Encounter",
        "id": "MHS-CON-001",
        "status": "finished",
        "subject": {"reference": "http://127.0.0.1/mini-his/Patient/MHS-PAT-001"},
        "period": {"start": "2026-09-01T15:00:00Z", "end": "2026-09-01T15:00:00Z"},
        "meta": {"source": "https://lab.local/mini-his"},
    }
    observation = _observation("mini-his", "MHS-RES-001", 13.4)
    observation["issued"] = "2026-09-01T15:10:00Z"
    observation["subject"] = {"reference": "http://127.0.0.1/mini-his/Patient/MHS-PAT-001"}
    observation["encounter"] = {"reference": "http://127.0.0.1/mini-his/Encounter/MHS-CON-001"}
    lis = _observation("mini-lis", "MLS-OBS-001", 141)
    lis["subject"] = {"reference": "http://127.0.0.1:18196/Patient/MLS-PAT-001"}
    federation = FederationDouble(
        _envelope(
            "complete",
            [
                {"sourceKey": "mini-his", "organizationId": "org-mini-his", "outcome": "complete", "resourceCount": 3},
                {"sourceKey": "mini-lis", "organizationId": "org-mini-lis", "outcome": "complete", "resourceCount": 1},
            ],
            [
                _entry("mini-his", _patient()),
                _entry("mini-his", encounter),
                _entry("mini-his", observation),
                _entry("mini-lis", lis),
            ],
        )
    )
    client = GuardClient()
    ports = LivePorts(
        _settings(clinical_context_mode="federated"),
        FollowUpReviewCaseService(repository),
        client,
        federation,
    )
    view = start_workflow(SqliteCheckpointSaver(tmp_path / "agent-workflow.sqlite3"), ports, "MHS-PAT-001", POST)
    assert client.calls == 0
    assert view["status"] == "waiting_human"
    assert view["evidence"] == ["Encounter/MHS-CON-001", "Observation/MHS-RES-001"]
    case = repository.get(view["reviewCaseId"])
    assert "mini-his" in case.narrative_text
    assert "mini-lis" in case.narrative_text
    assert "13.4" in case.narrative_text
    assert "141" in case.narrative_text
    assert "diagnostico" not in case.narrative_text.lower()
    html = _one_workflow(case, view)
    assert "origen mini-his" in html
    assert "Esta lectura no es una revisión clínica completa." not in html
    assert set(case.matched_resources) == set(view["evidence"])


def test_same_local_identifier_does_not_pair_another_source(tmp_path):
    from datetime import datetime, timezone

    from app.federated_protocol_evaluation import evaluate_federated_protocol

    encounter = {
        "resourceType": "Encounter",
        "id": "ENC-1",
        "status": "finished",
        "subject": {"reference": "http://127.0.0.1/mini-his/Patient/PAT-1"},
        "period": {"start": "2026-09-01T15:00:00Z", "end": "2026-09-01T15:00:00Z"},
        "meta": {"source": "https://lab.local/mini-his"},
    }
    lis_observation = _observation("mini-lis", "OBS-1", 13.4)
    lis_observation["issued"] = "2026-09-01T15:10:00Z"
    lis_observation["code"] = {"coding": [{"system": "https://lab.local/tests", "code": "GLU"}]}
    lis_observation["subject"] = {"reference": "http://127.0.0.1/mini-lis/Patient/PAT-1"}
    lis_observation["encounter"] = {"reference": "http://127.0.0.1/mini-lis/Encounter/ENC-1"}
    foreign = _observation("mini-his", "OBS-FOREIGN", 13.4)
    foreign["issued"] = "2026-09-01T15:10:00Z"
    foreign["subject"] = {"reference": "http://127.0.0.1/mini-lis/Patient/PAT-1"}
    foreign["encounter"] = {"reference": "http://127.0.0.1/mini-lis/Encounter/ENC-1"}
    patient = _patient()
    patient["id"] = "PAT-1"
    envelope = _envelope(
        "complete",
        [
            {"sourceKey": "mini-his", "organizationId": "org-mini-his", "outcome": "complete", "resourceCount": 3},
            {"sourceKey": "mini-lis", "organizationId": "org-mini-lis", "outcome": "complete", "resourceCount": 1},
        ],
        [
            _entry("mini-his", patient),
            _entry("mini-his", encounter),
            _entry("mini-his", foreign),
            _entry("mini-lis", lis_observation),
        ],
    )
    result, review = evaluate_federated_protocol(envelope, POST, datetime(2026, 10, 1, tzinfo=timezone.utc))
    assert review is None
    assert result["evaluationStatus"] == "insufficient"
    assert "final_observation_missing" in result["reasonCodes"]
    assert result["evidence"] == []


def test_colliding_observation_keeps_caller_source_in_review(tmp_path):
    from app.followup_review import FollowUpReviewCaseService
    from app.followup_review_sqlite import SQLiteFollowUpReviewCaseRepository
    from app.human_review_client import _one_workflow

    repository = SQLiteFollowUpReviewCaseRepository(tmp_path / "review.sqlite3")
    repository.initialize()
    encounter = {
        "resourceType": "Encounter",
        "id": "ENC-1",
        "status": "finished",
        "subject": {"reference": "http://127.0.0.1/mini-his/Patient/MHS-PAT-001"},
        "period": {"start": "2026-09-01T15:00:00Z", "end": "2026-09-01T15:00:00Z"},
        "meta": {"source": "https://lab.local/mini-his"},
    }
    his = _observation("mini-his", "OBS-1", 13.4)
    his["issued"] = "2026-09-01T15:10:00Z"
    his["code"] = {"coding": [{"system": "https://lab.local/tests", "code": "HB"}]}
    his["subject"] = {"reference": "http://127.0.0.1/mini-his/Patient/MHS-PAT-001"}
    his["encounter"] = {"reference": "http://127.0.0.1/mini-his/Encounter/ENC-1"}
    lis = _observation("mini-lis", "OBS-1", 13.4)
    lis["issued"] = "2026-09-01T15:10:00Z"
    lis["code"] = {"coding": [{"system": "https://lab.local/tests", "code": "HB"}]}
    lis["subject"] = {"reference": "http://127.0.0.1/mini-lis/Patient/MHS-PAT-001"}
    lis["encounter"] = {"reference": "http://127.0.0.1/mini-lis/Encounter/ENC-1"}
    federation = FederationDouble(
        _envelope(
            "complete",
            [
                {"sourceKey": "mini-his", "organizationId": "org-mini-his", "outcome": "complete", "resourceCount": 3},
                {"sourceKey": "mini-lis", "organizationId": "org-mini-lis", "outcome": "complete", "resourceCount": 2},
            ],
            [
                _entry("mini-lis", lis),
                _entry("mini-his", _patient()),
                _entry("mini-his", encounter),
                _entry("mini-his", his),
            ],
        )
    )
    ports = LivePorts(
        _settings(clinical_context_mode="federated"),
        FollowUpReviewCaseService(repository),
        GuardClient(),
        federation,
    )
    view = start_workflow(SqliteCheckpointSaver(tmp_path / "agent-workflow.sqlite3"), ports, "MHS-PAT-001", POST)
    assert view["status"] == "waiting_human"
    assert view["evidence"] == ["Encounter/ENC-1", "Observation/OBS-1"]
    case = repository.get(view["reviewCaseId"])
    assert set(case.matched_resources) == {"Encounter/ENC-1", "Observation/OBS-1"}
    assert "origen=mini-his" in case.narrative_text
    assert "origen=mini-lis" in case.narrative_text
    assert case.narrative_text.index("origen=mini-his") < case.narrative_text.index("Otra evidencia")
    observations = [
        item
        for item in view["clinicalContext"]["federation"]["resources"]
        if item["resourceType"] == "Observation"
    ]
    assert {item["sourceKey"] for item in observations} == {"mini-his", "mini-lis"}
    assert {item["fullUrl"] for item in observations} == {
        "http://127.0.0.1/mini-his/Observation/OBS-1",
        "http://127.0.0.1/mini-lis/Observation/OBS-1",
    }
    assert {item["source"] for item in observations} == {
        "https://lab.local/mini-his",
        "https://lab.local/mini-lis",
    }
    html = _one_workflow(case, view)
    assert "Observation/OBS-1 origen mini-his" in html
    assert "Observation/OBS-1 origen mini-lis" not in html


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

