"""Lab summary through federation, MCP, the neutral gateway, and pending review."""
import json
import socket
from io import StringIO

import httpx
import pytest

from app.clinical_federation_client import ClinicalFederationClient
from app.clinical_lab_summary.consent import PHRASE, OperationalClinicalConsent
from app.clinical_lab_summary.context import minimize_envelope
from app.clinical_lab_summary.graph import LabSummaryGraph
from app.clinical_lab_summary.mcp_tool import handle, read_chart
from app.clinical_lab_summary.once import run as demo_run
from app.clinical_lab_summary.review import read_status
from app.enterprise_ai_processing.execution_types import ExecutionError
from app.enterprise_ai_processing.remote_authorization import CLINICAL_OPERATION_ID, CLINICAL_POLICY_REF
from app.enterprise_llm_providers.errors import ProviderError
from app.model_gateway.egress_gemini import OperationalGeminiConsent
from app.model_gateway.gateway import NeutralModelGateway
from app.model_gateway.sdk_bridge import gemini_operational_reservation
from tests.test_model_gateway_durable_authorization import _gateway, _ready, _register
from tests.test_model_gateway_egress_gemini import KEY, _body, _consent as _vacation_consent


PATIENT = "MHS-PAT-001"
DEPLOYMENT = "gemini-sdk-a"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("provider socket forbidden")

    monkeypatch.setattr(socket, "socket", forbidden)


def _open_clinical(lab):
    try:
        lab.ledger.migrate_to_v6(lab.admin["ORG-A"])
    except ExecutionError as error:
        if error.reason != "revision_conflict":
            raise


def _permit(lab, authorization_id, **overrides):
    values = dict(
        authorization_id=authorization_id, deployment_id=DEPLOYMENT, provider_id="gemini",
        model_id="gemini-3.5-flash-lite", resource_id=PATIENT,
        budget_ceiling_microusd=1000, operation_id=CLINICAL_OPERATION_ID,
        policy_ref=CLINICAL_POLICY_REF)
    values.update(overrides)
    return _register(lab, **values)


def _clinical_consent(lab, authorization_id, client=None):
    access = lab.executor["ORG-A"]
    return OperationalClinicalConsent.issue(
        {"GEMINI_API_KEY": KEY}, authorization_id=authorization_id, deployment_id=DEPLOYMENT,
        organization_id="ORG-A", principal_id=access.principal_id, resource_id=PATIENT,
        phrase=PHRASE, interactive=True, http_client=client)


def _summary():
    return json.dumps({
        "kind": "lab-result-summary-v1",
        "review": "pending_human_review",
        "statements": [{
            "text": "Hemoglobina 13.4 g/dL en HIS y 7.1 mg/dL en LIS.",
            "sources": [
                {"source": "mini-his", "resourceType": "Observation", "id": "MHS-OBS-001"},
                {"source": "mini-lis", "resourceType": "Observation", "id": "MLS-OBS-001"},
            ],
        }],
    })


def _observation(source, observation_id, value, unit):
    return {
        "sourceKey": source,
        "resource": {
            "resourceType": "Observation",
            "id": observation_id,
            "status": "final",
            "code": {"coding": [{"system": "http://loinc.org", "code": "718-7"}]},
            "valueQuantity": {
                "value": value,
                "unit": unit,
                "system": "http://unitsofmeasure.org",
                "code": unit,
            },
        },
    }


def _envelope(status="complete", lis="complete"):
    return {
        "contractVersion": "clinical-federation-v1",
        "status": status,
        "truncated": False,
        "correlationId": "FED-CLINICAL0000001",
        "sources": [
            {"sourceKey": "mini-his", "outcome": "complete"},
            {"sourceKey": "mini-lis", "outcome": lis},
        ],
        "entries": [
            {"sourceKey": "mini-his", "resource": {
                "resourceType": "Patient", "id": PATIENT, "name": [{"family": "Quispe"}]}},
            _observation("mini-his", "MHS-OBS-001", 13.4, "g/dL"),
            _observation("mini-lis", "MLS-OBS-001", 7.1, "mg/dL"),
        ],
    }


def _federation(payload):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=payload, request=request)

    client = ClinicalFederationClient(
        "http://127.0.0.1:8081", "synthetic-token", organization_id="org-mini-his",
        patient_system_key="mini-his",
        patient_identifier_system="https://lab.local/mini-his/patient",
        sources=("mini-his", "mini-lis"),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    return client, requests


def _gemini(handler):
    requests = []

    def wrapped(request):
        requests.append(request)
        return handler(request)

    return httpx.Client(transport=httpx.MockTransport(wrapped)), requests


def _graph(lab, federation, review, audit=None):
    return LabSummaryGraph(
        _gateway(lab), federation, audit or (lambda event: None), review)


def _held(lab):
    import sqlite3
    with sqlite3.connect(lab.ledger.path) as connection:
        return [row[0] for row in connection.execute(
            "SELECT status FROM aip_remote_execution_reservation")]


def test_the_graph_reads_both_sources_and_queues_review(tmp_path):
    lab = _ready(tmp_path)
    try:
        _open_clinical(lab)
        _permit(lab, "lab-ok")
        federation, reads = _federation(_envelope())
        gemini, sends = _gemini(lambda request: httpx.Response(200, json=_body(_summary()), request=request))
        consent = _clinical_consent(lab, "lab-ok", gemini)
        review = tmp_path / "review.sqlite3"
        graph = _graph(lab, federation, review)
        state = graph.invoke(lab.executor["ORG-A"], "lab-ok", 1000, PATIENT, consent)
        assert state["phase"] == "PENDING_REVIEW"
        assert state["reason"] == "pending_human_review"
        assert state["review_status"] == "pending"
        assert state["requests_sent"] == 1 and graph.model_calls == 1
        assert state["reserved_microusd"] == gemini_operational_reservation()
        assert state["cost_kind"] == "estimated" and state["input_tokens"] == 40
        assert len(reads) == 1 and len(sends) == 1
        assert read_status(review, _review_id(review)) == "pending"
        rendered = json.dumps(state)
        assert "Quispe" not in rendered and KEY not in rendered
        again = graph.invoke(lab.executor["ORG-A"], "lab-ok", 1000, PATIENT, consent)
        assert again["reason"] == "replay_denied" and len(sends) == 1 and graph.model_calls == 1
    finally:
        lab.close()


def test_provider_failures_do_not_retry_or_accept(tmp_path):
    lab = _ready(tmp_path)
    try:
        _open_clinical(lab)

        def timeout(request):
            raise httpx.ReadTimeout("slow")

        cases = (
            ("lab-timeout", timeout, "timeout"),
            ("lab-http", lambda request: httpx.Response(500, json={"error": "down"}, request=request),
             "remote_unavailable"),
            ("lab-bad", lambda request: httpx.Response(200, json=_body("not-json"), request=request),
             "invalid_output"),
        )
        for authorization_id, handler, reason in cases:
            _permit(lab, authorization_id)
            federation, reads = _federation(_envelope())
            gemini, sends = _gemini(handler)
            consent = _clinical_consent(lab, authorization_id, gemini)
            graph = _graph(lab, federation, tmp_path / (authorization_id + ".sqlite3"))
            state = graph.invoke(lab.executor["ORG-A"], authorization_id, 1000, PATIENT, consent)
            assert state["phase"] == "FAILED" and state["reason"] == reason
            assert state["requests_sent"] == 1 and len(sends) == 1 and len(reads) == 1
            assert state.get("review_status") is None
            again = graph.invoke(lab.executor["ORG-A"], authorization_id, 1000, PATIENT, consent)
            assert again["reason"] == "replay_denied" and len(sends) == 1
            lab.ledger.revoke_remote_authorization(
                lab.admin["ORG-A"], authorization_id, "operator_revoked")
        assert _held(lab).count("held") == 3
    finally:
        lab.close()


def test_budget_revocation_replay_and_audit_fail_closed(tmp_path):
    lab = _ready(tmp_path)
    try:
        _open_clinical(lab)
        _permit(lab, "lab-budget")
        federation, reads = _federation(_envelope())
        gemini, sends = _gemini(lambda request: httpx.Response(200, json=_body(_summary()), request=request))
        state = _graph(lab, federation, tmp_path / "budget.sqlite3").invoke(
            lab.executor["ORG-A"], "lab-budget", 500,
            PATIENT, _clinical_consent(lab, "lab-budget", gemini))
        assert state["reason"] == "budget_exceeded" and sends == []
        lab.ledger.revoke_remote_authorization(lab.admin["ORG-A"], "lab-budget", "operator_revoked")

        _permit(lab, "lab-revoked")
        lab.ledger.revoke_remote_authorization(lab.admin["ORG-A"], "lab-revoked", "operator_revoked")
        state = _graph(lab, federation, tmp_path / "revoked.sqlite3").invoke(
            lab.executor["ORG-A"], "lab-revoked", 1000, PATIENT,
            _clinical_consent(lab, "lab-revoked", gemini))
        assert state["reason"] == "revoked" and state["requests_sent"] == 0

        _permit(lab, "lab-replay")
        first = _graph(lab, federation, tmp_path / "replay.sqlite3")
        done = first.invoke(
            lab.executor["ORG-A"], "lab-replay", 1000, PATIENT,
            _clinical_consent(lab, "lab-replay", gemini))
        assert done["phase"] == "PENDING_REVIEW" and len(sends) == 1
        restarted = _graph(lab, federation, tmp_path / "replay.sqlite3")
        again = restarted.invoke(
            lab.executor["ORG-A"], "lab-replay", 1000, PATIENT,
            _clinical_consent(lab, "lab-replay", gemini))
        assert again["reason"] == "replay_denied" and again["requests_sent"] == 0 and len(sends) == 1
    finally:
        lab.close()


def test_audit_and_partial_chart_do_not_send(tmp_path):
    lab = _ready(tmp_path)
    try:
        _open_clinical(lab)
        _permit(lab, "lab-audit")
        federation, reads = _federation(_envelope())
        gemini, sends = _gemini(lambda request: httpx.Response(200, json=_body(_summary()), request=request))

        def fault(stage):
            if stage == "audit_remote_authorization_evaluated":
                raise OSError("disk")

        lab.ledger._fault = fault
        state = _graph(lab, federation, tmp_path / "audit.sqlite3").invoke(
            lab.executor["ORG-A"], "lab-audit", 1000, PATIENT,
            _clinical_consent(lab, "lab-audit", gemini))
        assert state["reason"] == "storage_unavailable" and sends == [] and len(reads) == 1
        lab.ledger._fault = lambda stage: None
        lab.ledger.revoke_remote_authorization(lab.admin["ORG-A"], "lab-audit", "operator_revoked")

        _permit(lab, "lab-partial")
        partial, partial_reads = _federation(_envelope(status="partial", lis="identity_unresolved"))
        state = _graph(lab, partial, tmp_path / "partial.sqlite3").invoke(
            lab.executor["ORG-A"], "lab-partial", 1000, PATIENT,
            _clinical_consent(lab, "lab-partial", gemini))
        assert state["reason"] == "context_incomplete" and sends == [] and len(partial_reads) == 1
    finally:
        lab.close()


def test_vacation_and_clinical_consents_do_not_cross(tmp_path):
    lab = _ready(tmp_path)
    try:
        _open_clinical(lab)
        _register(lab, authorization_id="vacation-row", deployment_id=DEPLOYMENT, provider_id="gemini",
                  model_id="gemini-3.5-flash-lite", budget_ceiling_microusd=1000)
        _permit(lab, "clinical-row")
        clinical = _clinical_consent(lab, "clinical-row")
        vacation = _vacation_consent(lab, "vacation-row")
        with pytest.raises(ProviderError) as clinical_on_vacation:
            _gateway(lab).execute(
                lab.executor["ORG-A"], "vacation-row", 1000, "vacation-a", DEPLOYMENT,
                egress_consent=clinical)
        with pytest.raises(ProviderError) as vacation_on_clinical:
            _gateway(lab).execute_lab_summary(
                lab.executor["ORG-A"], "clinical-row", 1000, PATIENT, DEPLOYMENT, {}, vacation,
                lambda summary: None)
        assert clinical_on_vacation.value.reason == "egress_blocked"
        assert vacation_on_clinical.value.reason == "egress_blocked"
        federation, reads = _federation(_envelope())
        state = _graph(lab, federation, tmp_path / "cross.sqlite3").invoke(
            lab.executor["ORG-A"], "vacation-row", 1000, PATIENT,
            _clinical_consent(lab, "vacation-row"))
        assert state["reason"] == "operation_denied" and reads
    finally:
        lab.close()


def test_sources_and_c03_stay_separated():
    graph = open(
        "app/clinical_lab_summary/graph.py", encoding="utf-8").read()
    assert "retry_policy=None" in graph
    assert "google" not in graph and "vacation-days-v1" not in graph
    enterprise = open("app/enterprise_ai_processing/gateway.py", encoding="utf-8").read()
    assert "type(self.model) is FakeEnterpriseModel" in enterprise


def test_the_demo_command_stops_before_a_client():
    with pytest.raises(ProviderError) as missing:
        demo_run(StringIO(""), {})
    assert missing.value.reason == "confirmation_required"


def test_mcp_handshake_ignores_model_supplied_authority():
    federation, reads = _federation(_envelope())
    events = []
    bound = {
        "authorization_id": "lab-ok", "principal_id": "synthetic-executor",
        "patient_id": PATIENT, "operation_id": "lab-result-summary-v1",
    }
    reply = read_chart(bound, federation, events.append)
    chart = json.loads(reply["result"]["content"][0]["text"])
    assert chart["patient_id"] == PATIENT and len(reads) == 1
    assert [item["reason"] for item in events] == ["tool_started", "tool_completed"]
    unknown = handle({"jsonrpc": "2.0", "id": 9, "method": "resources/list"}, bound, federation, events.append)
    assert unknown["error"]["message"] == "method_not_found" and len(reads) == 1
    bare = handle({"method": "tools/call"}, bound, federation, events.append)
    assert bare["error"]["message"] == "invalid_request"
    stolen = handle(
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
         "params": {"name": "read_federated_lab_chart",
                    "arguments": {"patient_id": "MHS-PAT-002", "authorization_id": "model-grant"}}},
        bound, federation, events.append)
    assert stolen["error"]["message"] == "scope_mismatch" and len(reads) == 1

    def refuse(event):
        raise OSError("disk")

    with pytest.raises(ProviderError) as caught:
        read_chart(bound, federation, refuse)
    assert caught.value.reason == "audit_unavailable" and len(reads) == 1


def test_text_coded_laboratory_fact_is_kept_and_a_panel_is_omitted():
    envelope = _envelope()
    envelope["entries"].append({
        "sourceKey": "mini-his",
        "resource": {
            "resourceType": "Observation", "id": "MHS-RES-001", "status": "final",
            "code": {"text": "Hemoglobina"},
            "valueQuantity": {
                "value": 13.4,
                "unit": "g/dL",
                "system": "http://unitsofmeasure.org",
                "code": "g/dL",
            },
        },
    })
    envelope["entries"].append({
        "sourceKey": "mini-his",
        "resource": {
            "resourceType": "Observation", "id": "MHS-RES-002", "status": "final",
            "code": {"text": "Presion arterial"},
            "component": [{"code": {"text": "Presion sistolica"}}],
        },
    })
    chart = minimize_envelope(envelope, PATIENT)
    assert {item["id"] for item in chart["facts"]} >= {"MHS-OBS-001", "MHS-RES-001", "MLS-OBS-001"}
    assert "MHS-RES-002" not in {item["id"] for item in chart["facts"]}
    assert "Quispe" not in json.dumps(chart)


def test_an_uncoded_or_contradictory_unit_is_not_sent_to_the_model():
    envelope = _envelope()
    envelope["entries"] = [
        entry for entry in envelope["entries"]
        if entry["resource"].get("id") != "MLS-OBS-001"
    ]
    envelope["entries"].append({
        "sourceKey": "mini-lis",
        "resource": {
            "resourceType": "Observation", "id": "MLS-GLU-OLD", "status": "final",
            "code": {"coding": [{"system": "https://lab.local/mini-lis/test", "code": "GLU"}]},
            "valueQuantity": {"value": 141, "unit": "mmol/L"},
            "referenceRange": [{"text": "70-110"}],
        },
    })
    with pytest.raises(ProviderError) as missing:
        minimize_envelope(envelope, PATIENT)
    assert missing.value.reason == "context_incomplete"

    coded = {
        "sourceKey": "mini-lis",
        "resource": {
            "resourceType": "Observation", "id": "MLS-GLU-NEW", "status": "final",
            "code": {"coding": [{"system": "https://lab.local/mini-lis/test", "code": "GLU"}]},
            "valueQuantity": {
                "value": 141, "unit": "mg/dL",
                "system": "http://unitsofmeasure.org", "code": "mg/dL",
            },
            "referenceRange": [{
                "low": {"value": 70, "unit": "mg/dL", "system": "http://unitsofmeasure.org", "code": "mg/dL"},
                "high": {"value": 110, "unit": "mmol/L", "system": "http://unitsofmeasure.org", "code": "mmol/L"},
            }],
        },
    }
    envelope["entries"].append(coded)
    with pytest.raises(ProviderError) as contradictory:
        minimize_envelope(envelope, PATIENT)
    assert contradictory.value.reason == "context_incomplete"

    coded["resource"]["referenceRange"] = [{
        "low": {"value": 70, "unit": "mg/dL", "system": "http://unitsofmeasure.org", "code": "mg/dL"},
        "high": {"value": 110, "unit": "mg/dL", "system": "http://unitsofmeasure.org", "code": "mg/dL"},
    }]
    chart = minimize_envelope(envelope, PATIENT)
    lis = [item for item in chart["facts"] if item["source"] == "mini-lis"]
    assert lis == [{
        "source": "mini-lis",
        "resourceType": "Observation",
        "id": "MLS-GLU-NEW",
        "status": "final",
        "code": "GLU",
        "value": "141",
        "unit": "mg/dL",
    }]
    assert "mmol/L" not in json.dumps(chart)
    assert "MLS-GLU-OLD" not in {item["id"] for item in chart["facts"]}
    rest = [entry for entry in envelope["entries"] if entry["sourceKey"] != "mini-lis"]
    lis_entries = [entry for entry in envelope["entries"] if entry["sourceKey"] == "mini-lis"]
    envelope["entries"] = rest + list(reversed(lis_entries))
    again = minimize_envelope(envelope, PATIENT)
    assert again["facts"] == chart["facts"]


def test_v6_rolls_back_and_keeps_the_v5_permit(tmp_path):
    lab = _ready(tmp_path)
    try:
        record = _register(
            lab, authorization_id="keep-vacation", deployment_id=DEPLOYMENT, provider_id="gemini",
            model_id="gemini-3.5-flash-lite", budget_ceiling_microusd=1000)
        decision = lab.ledger.evaluate_remote_authorization(
            lab.executor["ORG-A"], record, requested_budget_microusd=1000)
        assert decision.reason == "accepted" and _version(lab) == 5
        before = _permit_rows(lab)
        lab.ledger._fault = _fail_before_v6
        with pytest.raises(ExecutionError):
            lab.ledger.migrate_to_v6(lab.admin["ORG-A"])
        assert _version(lab) == 5 and _permit_rows(lab) == before
        lab.ledger._fault = lambda stage: None
        lab.ledger.migrate_to_v6(lab.admin["ORG-A"])
        assert _version(lab) == 6 and _permit_rows(lab) == before
        with pytest.raises(ExecutionError) as repeated:
            lab.ledger.migrate_to_v6(lab.admin["ORG-A"])
        assert repeated.value.reason == "revision_conflict"
        with pytest.raises(ExecutionError):
            _register(
                lab, authorization_id="mixed-policy", deployment_id=DEPLOYMENT, provider_id="gemini",
                model_id="gemini-3.5-flash-lite", budget_ceiling_microusd=1000,
                operation_id=CLINICAL_OPERATION_ID, policy_ref="model-gateway-policy-v1")
        _permit(lab, "clinical-after-v6")
        denied = lab.ledger.evaluate_remote_authorization(
            lab.executor["ORG-A"], _record_for(lab, "keep-vacation", CLINICAL_OPERATION_ID, CLINICAL_POLICY_REF),
            requested_budget_microusd=1000)
        assert denied.reason == "operation_denied"
    finally:
        lab.close()


def _fail_before_v6(stage):
    if stage == "migrate_v6_before_commit":
        raise OSError("disk")


def _version(lab):
    import sqlite3
    with sqlite3.connect(lab.ledger.path) as connection:
        return connection.execute("SELECT schema_version FROM aip_store").fetchone()[0]


def _permit_rows(lab):
    import sqlite3
    with sqlite3.connect(lab.ledger.path) as connection:
        permits = connection.execute(
            "SELECT authorization_id, operation_id, policy_ref, status "
            "FROM aip_remote_execution_permit ORDER BY authorization_id").fetchall()
        reservations = connection.execute(
            "SELECT authorization_id, status FROM aip_remote_execution_reservation "
            "ORDER BY authorization_id").fetchall()
    return permits, reservations


def _record_for(lab, authorization_id, operation_id, policy_ref):
    from datetime import timedelta
    from app.enterprise_ai_processing.remote_authorization import RemoteAuthorization
    now = lab.clock()
    return RemoteAuthorization(
        authorization_id, "ORG-A", DEPLOYMENT, "gemini", "gemini-3.5-flash-lite",
        now - timedelta(minutes=1), now + timedelta(minutes=5), operation_id=operation_id,
        policy_ref=policy_ref, principal_id="synthetic-executor", resource_id="vacation-a",
        budget_ceiling_microusd=1000)


def _review_id(path):
    import sqlite3
    with sqlite3.connect(path) as connection:
        return connection.execute("SELECT review_id FROM lab_summary_review").fetchone()[0]
