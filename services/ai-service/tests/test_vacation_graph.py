"""LangGraph vacation-days flow. The network mock never leaves the process."""
import ast
import json
import socket
from io import StringIO
from pathlib import Path

import httpx
import pytest

from app.enterprise_ai_processing.fake_model import FakeEnterpriseModel
from app.enterprise_llm_providers.errors import ProviderError
from app.enterprise_llm_providers.vacation_graph import VacationGraph
from app.enterprise_llm_providers.vacation_graph_once import run as graph_run
from app.enterprise_llm_providers.smoke import FIXED_DOCUMENT
from app.model_gateway.egress_gemini import PHRASE
from app.model_gateway.sdk_bridge import gemini_operational_reservation
from tests.test_model_gateway_egress_gemini import (
    DEPLOYMENT, KEY, _body, _consent, _http, _mock, _permit, _status,
)
from tests.test_model_gateway_durable_authorization import RESOURCE, _gateway, _ready


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("provider socket forbidden")))


def _invoke(lab, consent, authorization_id="egress-g", budget=1000, graph=None):
    chosen = graph or VacationGraph(_gateway(lab))
    return chosen, chosen.invoke(
        lab.executor["ORG-A"], authorization_id, budget, RESOURCE, DEPLOYMENT, egress_consent=consent)


def test_the_graph_reaches_gemini_once_and_records_the_public_result(tmp_path):
    lab = _ready(tmp_path)
    try:
        _permit(lab)
        client, requests = _mock(_http(200, _body()))
        consent = _consent(lab, client=client)
        graph, state = _invoke(lab, consent)
        assert state["phase"] == "COMPLETED" and state["reason"] == "accepted"
        assert state["input_tokens"] == 40 and state["output_tokens"] == 16
        assert state["reserved_microusd"] == gemini_operational_reservation() == 977
        assert state["cost_kind"] == "estimated" and state["provider_request_id"] == "resp_gemini_test"
        assert graph.model_calls == 1 and consent.requests_sent == 1 and len(requests) == 1
        assert _status(lab) == ["consumed"]
        assert "source_excerpt" not in state and FIXED_DOCUMENT not in json.dumps(state)
        assert KEY not in json.dumps(state)
        again = graph.invoke(
            lab.executor["ORG-A"], "egress-g", 1000, RESOURCE, DEPLOYMENT, egress_consent=consent)
        assert again["reason"] == "replay_denied" and graph.model_calls == 1 and len(requests) == 1
    finally:
        lab.close()


def test_provider_timeout_invalid_output_and_audit_do_not_retry(tmp_path):
    lab = _ready(tmp_path)
    try:
        def timeout(request):
            raise httpx.ReadTimeout("slow")

        cases = (
            ("egress-timeout", timeout, "timeout"),
            ("egress-http", _http(500, {"error": {"message": "down", "code": 500}}), "remote_unavailable"),
            ("egress-bad", _http(200, _body("not-json")), "invalid_output"),
        )
        for authorization_id, handler, reason in cases:
            _permit(lab, authorization_id)
            client, requests = _mock(handler)
            consent = _consent(lab, authorization_id, client=client)
            graph, state = _invoke(lab, consent, authorization_id)
            assert state["phase"] == "FAILED" and state["reason"] == reason
            assert graph.model_calls == 1 and len(requests) == 1 and KEY not in json.dumps(state)
            second = graph.invoke(
                lab.executor["ORG-A"], authorization_id, 1000, RESOURCE, DEPLOYMENT, egress_consent=consent)
            assert second["reason"] == "replay_denied" and len(requests) == 1
            lab.ledger.revoke_remote_authorization(lab.admin["ORG-A"], authorization_id, "operator_revoked")
        _permit(lab, "egress-audit")

        def fault(stage):
            if stage == "audit_remote_authorization_evaluated":
                raise OSError("disk")

        lab.ledger._fault = fault
        consent = _consent(lab, "egress-audit", client=_mock(_http(200, _body()))[0])
        graph, state = _invoke(lab, consent, "egress-audit")
        assert state["reason"] == "storage_unavailable" and graph.model_calls == 1 and consent.requests_sent == 0
        assert _status(lab).count("held") == 3
    finally:
        lab.close()


def test_budget_revocation_and_restart_stay_closed(tmp_path):
    lab = _ready(tmp_path)
    try:
        _permit(lab, "egress-budget")
        consent = _consent(lab, "egress-budget", client=_mock(_http(200, _body()))[0])
        graph, state = _invoke(lab, consent, "egress-budget", budget=500)
        assert state["reason"] == "budget_exceeded" and graph.model_calls == 1 and consent.requests_sent == 0
        lab.ledger.revoke_remote_authorization(lab.admin["ORG-A"], "egress-budget", "operator_revoked")
        _permit(lab, "egress-revoked")
        lab.ledger.revoke_remote_authorization(lab.admin["ORG-A"], "egress-revoked", "operator_revoked")
        revoked = _consent(lab, "egress-revoked", client=_mock(_http(200, _body()))[0])
        _, denied = _invoke(lab, revoked, "egress-revoked")
        assert denied["reason"] == "revoked" and revoked.requests_sent == 0
        _permit(lab, "egress-once")
        client, requests = _mock(_http(200, _body()))
        ok = _consent(lab, "egress-once", client=client)
        first = VacationGraph(_gateway(lab))
        done = first.invoke(lab.executor["ORG-A"], "egress-once", 1000, RESOURCE, DEPLOYMENT, egress_consent=ok)
        assert done["phase"] == "COMPLETED" and len(requests) == 1
        root, issuer, clock = lab.ledger.root, lab.issuer, lab.clock
        lab.ledger.close()
        from app.enterprise_ai_processing.sqlite_ledger import SQLiteExecutionLedger
        from app.enterprise_ai_processing.durable_resolver import LedgerDurableAuthorization
        from app.model_gateway.gateway import NeutralModelGateway
        reopened = SQLiteExecutionLedger(root, issuer, clock)
        try:
            restarted = VacationGraph(NeutralModelGateway(resolver=LedgerDurableAuthorization(reopened)))
            fresh = _consent(lab, "egress-once", client=_mock(_http(200, _body()))[0])
            after = restarted.invoke(
                lab.executor["ORG-A"], "egress-once", 1000, RESOURCE, DEPLOYMENT, egress_consent=fresh)
            assert after["reason"] == "replay_denied" and fresh.requests_sent == 0 and len(requests) == 1
        finally:
            reopened.close()
    finally:
        lab.close()


def test_default_path_clinical_graph_and_c03_stay_separate(tmp_path):
    lab = _ready(tmp_path)
    try:
        _permit(lab, "egress-off")
        graph, state = _invoke(lab, None, "egress-off")
        assert state["reason"] == "remote_disabled" and graph.model_calls == 1
        assert _status(lab) == ["held"]
    finally:
        lab.close()
    package = Path(__file__).resolve().parents[1] / "app"
    graph_source = (package / "enterprise_llm_providers" / "vacation_graph.py").read_text(encoding="utf-8")
    tree = ast.parse(graph_source)
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    assert "google" not in " ".join(imported) and "openai" not in " ".join(imported)
    assert "langgraph_gemini_fhir_followup" not in graph_source
    assert "retry_policy=None" in graph_source
    enterprise = (package / "enterprise_ai_processing" / "gateway.py").read_text(encoding="utf-8")
    assert "type(self.model) is FakeEnterpriseModel" in enterprise and FakeEnterpriseModel is not None


def test_the_demo_command_stops_before_a_client(tmp_path):
    class _TTY(StringIO):
        def isatty(self):
            return True

    with pytest.raises(ProviderError) as quiet:
        graph_run(StringIO(PHRASE + "\n"), {"LOCALAPPDATA": str(tmp_path), "GEMINI_API_KEY": KEY})
    with pytest.raises(ProviderError) as wrong:
        graph_run(_TTY("no\n"), {"LOCALAPPDATA": str(tmp_path), "GEMINI_API_KEY": KEY})
    with pytest.raises(ProviderError) as missing:
        graph_run(_TTY(PHRASE + "\n"), {"LOCALAPPDATA": str(tmp_path)})
    assert quiet.value.reason == wrong.value.reason == "confirmation_required"
    assert missing.value.reason == "credential_absent"
    assert KEY not in str(quiet.value)
