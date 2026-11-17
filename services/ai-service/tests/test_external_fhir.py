"""External FHIR chart with an intercepted federation response and an intercepted model."""
import json
from pathlib import Path

import httpx

from app.clinical_federation_client import ClinicalFederationClient
from app.clinical_lab_summary.http import _detail
from app.clinical_lab_summary.review import read_review, read_status, review_organization
from app.enterprise_llm_providers.errors import ProviderError
from app.external_fhir.context import minimize_envelope
from app.external_fhir.graph import ExternalFhirGraph
from app.external_fhir.mcp_tool import TOOL_NAME, handle
from app.external_fhir.policy import (
    AUTHORIZATION_ID,
    IDENTIFIER_SYSTEM,
    OPERATION_ID,
    PATIENT_ID,
    SOURCE,
)


REVIEW_ID = "11111111-1111-4111-8111-111111111111"
OBSERVATION_ID = "obs-verified"


class Access:
    mode = "development"
    permissions = frozenset()
    csrf = ""


def test_intercepted_graph_queues_pending_review_with_external_provenance(tmp_path):
    audits = []
    graph = ExternalFhirGraph(client(_handler(verified=True)), audits.append, tmp_path / "review.sqlite3", _transport)
    state = graph.invoke(REVIEW_ID)

    assert state["phase"] == "PENDING_REVIEW"
    assert state["reason"] == "pending_human_review"
    assert state["requests_sent"] == 1
    assert state["operation_id"] == OPERATION_ID
    assert read_status(tmp_path / "review.sqlite3", REVIEW_ID) == "pending"
    assert review_organization(tmp_path / "review.sqlite3", REVIEW_ID) == "org-smart-sandbox"
    case = read_review(tmp_path / "review.sqlite3", REVIEW_ID)
    page = _detail(case, Access())
    assert SOURCE in page
    assert OBSERVATION_ID in page
    assert "pending" in page
    assert "obs-unverified" not in json.dumps(state["chart"])
    assert [item["reason"] for item in audits] == ["tool_started", "tool_completed"]
    try:
        graph.invoke(REVIEW_ID)
    except ProviderError as error:
        assert error.reason == "replay_denied"
    else:
        raise AssertionError("replay")


def test_missing_transport_does_not_queue_a_review(tmp_path):
    path = tmp_path / "review.sqlite3"
    graph = ExternalFhirGraph(client(_handler(verified=True)), lambda _event: None, path)
    try:
        graph.invoke(REVIEW_ID)
    except ProviderError as error:
        assert error.reason == "model_denied"
    else:
        raise AssertionError("model")
    assert not path.exists()


def test_tool_rejects_another_permit_and_an_arbitrary_endpoint():
    bound = {
        "operation_id": "vacation-days-v1",
        "patient_id": PATIENT_ID,
        "authorization_id": AUTHORIZATION_ID,
    }
    denied = handle(
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": TOOL_NAME, "arguments": {"patient_id": PATIENT_ID}}},
        bound, client(_handler(verified=True)), lambda _event: None)
    assert denied["error"]["message"] == "remote_not_authorized"
    lab = ClinicalFederationClient(
        "http://127.0.0.1:18281", "lab-token", organization_id="org-mini-his",
        patient_system_key="mini-his", patient_identifier_system=IDENTIFIER_SYSTEM,
        sources=("mini-his", "mini-lis"))
    wrong_client = handle(
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": TOOL_NAME, "arguments": {"patient_id": PATIENT_ID}}},
        _bound(), lab, lambda _event: None)
    assert wrong_client["error"]["message"] == "tool_denied"
    arbitrary = handle(
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": TOOL_NAME, "arguments": {"patient_id": PATIENT_ID, "endpoint": "https://evil.example"}}},
        _bound(), client(_handler(verified=True)), lambda _event: None)
    assert arbitrary["error"]["message"] == "scope_mismatch"


def test_unverified_quantity_is_not_a_model_fact():
    chart = minimize_envelope(_envelope(include_unverified=True), PATIENT_ID)
    assert [item["id"] for item in chart["facts"]] == [OBSERVATION_ID]
    assert chart["facts"][0]["unit"] == "mg/dL"
    assert "name" not in json.dumps(chart)


def test_package_does_not_call_a_provider_sdk():
    root = Path(__file__).parents[1] / "app" / "external_fhir"
    source = "\n".join(path.read_text(encoding="utf-8") for path in root.glob("*.py"))
    assert "google.genai" not in source
    assert "openai" not in source
    assert "execute_lab_summary" not in source
    assert "from app.model_gateway" not in source
    assert "import app.model_gateway" not in source


def _transport(chart):
    fact = chart["facts"][0]
    return {
        "kind": OPERATION_ID,
        "review": "pending_human_review",
        "statements": [{
            "text": "HDL " + fact["value"] + " " + fact["unit"],
            "sources": [{"source": SOURCE, "resourceType": "Observation", "id": fact["id"]}],
        }],
    }


def _bound():
    return {
        "operation_id": OPERATION_ID,
        "patient_id": PATIENT_ID,
        "authorization_id": AUTHORIZATION_ID,
    }


def client(handler):
    return ClinicalFederationClient(
        "http://127.0.0.1:18281", "lab-token", organization_id="org-mini-his",
        patient_system_key="mini-his", patient_identifier_system=IDENTIFIER_SYSTEM,
        sources=(SOURCE,), http_client=httpx.Client(transport=httpx.MockTransport(handler)))


def _handler(verified):
    def respond(request):
        assert request.method == "POST"
        assert request.url.path == "/api/clinical-federation/v1/context"
        assert "r4.smarthealthit.org" not in str(request.url)
        body = json.loads(request.content)
        assert body["sources"] == [SOURCE]
        assert body["patient"]["identifierValue"] == PATIENT_ID
        assert body["patient"]["identifierSystem"] == IDENTIFIER_SYSTEM
        return httpx.Response(200, json=_envelope(include_unverified=verified))
    return respond


def _envelope(include_unverified):
    entries = [_entry(_observation(OBSERVATION_ID, verified=True))]
    if include_unverified:
        entries.append(_entry(_observation("obs-unverified", verified=False)))
    entries.append(_entry({
        "resourceType": "Patient",
        "id": "remote-patient",
        "name": [{"family": "Synthetic"}],
    }))
    return {
        "contractVersion": "clinical-federation-v1",
        "status": "complete",
        "truncated": False,
        "sources": [{"sourceKey": SOURCE, "outcome": "complete"}],
        "entries": entries,
    }


def _entry(resource):
    return {"sourceKey": SOURCE, "resource": resource}


def _observation(observation_id, verified):
    quantity = {"value": 69.3, "unit": "mg/dL", "system": "http://unitsofmeasure.org", "code": "mg/dL"}
    if not verified:
        quantity = {"value": 83.7, "unit": "fL"}
    return {
        "resourceType": "Observation",
        "id": observation_id,
        "status": "final",
        "code": {"coding": [{"code": "2085-9"}]},
        "valueQuantity": quantity,
        "meta": {"tag": [{
            "system": "https://lab.local/external-fhir/verification",
            "code": "quantity-verified" if verified else "unit-not-verified",
        }]},
    }
