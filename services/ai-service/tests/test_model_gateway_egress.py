"""Controlled OpenAI egress. The network mock never leaves the process."""
import ast
import json
import logging
import socket
import sqlite3
import threading
from datetime import timedelta
from pathlib import Path

import httpx2
import pytest

from app.enterprise_ai_processing.fake_model import FakeEnterpriseModel
from app.enterprise_llm_providers.configuration import ProviderSettings
from app.enterprise_llm_providers.errors import ProviderError
from app.enterprise_llm_providers.egress_once import run as egress_run
from app.enterprise_llm_providers.gemini_configuration import GeminiSettings
from app.enterprise_llm_providers.gemini_request import build_generation
from app.enterprise_llm_providers.gemini_transport import GeminiSDKTransport
from app.enterprise_llm_providers.pricing import estimate_microusd
from app.enterprise_llm_providers.request import build_payload
from app.enterprise_llm_providers.smoke import FIXED_DOCUMENT
from app.enterprise_llm_providers.transport import OpenAISDKTransport, live_egress_enabled
from app.model_gateway.egress import PHRASE, OperationalEgressConsent
from app.model_gateway.sdk_bridge import openai_reservation
from tests.test_model_gateway_durable_authorization import RESOURCE, _gateway, _ready, _register


KEY = "sk-lab-not-a-real-key"
DEPLOYMENT = "openai-sdk-a"
PACKAGE = Path(__file__).resolve().parents[1] / "app"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("provider socket forbidden")

    monkeypatch.setattr(socket, "socket", forbidden)


def _permit(lab, authorization_id="egress-a", **overrides):
    values = dict(
        authorization_id=authorization_id, deployment_id=DEPLOYMENT, provider_id="openai",
        model_id="gpt-6-luna", budget_ceiling_microusd=1000, resource_id=RESOURCE)
    values.update(overrides)
    return _register(lab, **values)


def _consent(lab, authorization_id="egress-a", client=None, principal=None, resource=RESOURCE,
             phrase=PHRASE, interactive=True, mapping=None):
    access = lab.executor["ORG-A"]
    body = {"OPENAI_API_KEY": KEY} if mapping is None else mapping
    return OperationalEgressConsent.issue(
        body, authorization_id=authorization_id, deployment_id=DEPLOYMENT, organization_id="ORG-A",
        principal_id=access.principal_id if principal is None else principal, resource_id=resource,
        phrase=phrase, interactive=interactive, timeout_seconds=15, max_output_tokens=16,
        http_client=None if client is None else client)


def _mock(handler):
    requests = []

    def wrapped(request):
        requests.append(request)
        return handler(request)

    client = httpx2.Client(transport=httpx2.MockTransport(wrapped))
    return client, requests


def _body(text="{}"):
    return {
        "id": "resp_test", "created_at": 1, "model": "gpt-6-luna", "object": "response",
        "parallel_tool_calls": False, "tool_choice": "none", "tools": [], "status": "completed",
        "output": [{
            "id": "msg_test", "type": "message", "role": "assistant", "status": "completed",
            "content": [{"type": "output_text", "text": text, "annotations": []}],
        }],
        "usage": {"input_tokens": 32, "output_tokens": 16, "total_tokens": 48},
    }


def _observation():
    encoded = FIXED_DOCUMENT.encode("utf-8")
    return {
        "question_id": "vacation-days-v1", "evidence_found": True, "proposed_days": 20,
        "proposed_months": 12, "source_excerpt": FIXED_DOCUMENT, "evidence_start": 0,
        "evidence_end": len(encoded), "refusal_or_insufficient": False,
    }


def _http(status, payload):
    def handler(request):
        return httpx2.Response(status, json=payload, request=request)
    return handler


def _execute(gateway, lab, consent, authorization_id="egress-a", budget=1000, resource=RESOURCE, access=None):
    chosen = lab.executor["ORG-A"] if access is None else access
    return gateway.execute(
        chosen, authorization_id, budget, resource, DEPLOYMENT, egress_consent=consent)


def _status(lab):
    with sqlite3.connect(lab.ledger.path) as connection:
        rows = connection.execute("SELECT status FROM aip_remote_execution_reservation").fetchall()
    return [row[0] for row in rows]


def test_default_egress_stays_closed_and_a_later_consent_cannot_send(tmp_path):
    lab = _ready(tmp_path)
    try:
        _permit(lab, "egress-off")
        gateway = _gateway(lab)
        with pytest.raises(ProviderError) as blocked:
            gateway.execute(lab.executor["ORG-A"], "egress-off", 1000, RESOURCE, DEPLOYMENT)
        assert blocked.value.reason == "remote_disabled" and _status(lab) == ["held"]
        consent = _consent(lab, "egress-off", client=_mock(_http(200, _body()))[0])
        with pytest.raises(ProviderError) as replay:
            _execute(gateway, lab, consent, "egress-off")
        assert replay.value.reason == "replay_denied" and consent.requests_sent == 0
        assert live_egress_enabled() is False
    finally:
        lab.close()


def test_missing_consent_credential_and_phrase_do_not_hold_a_permit(tmp_path):
    lab = _ready(tmp_path)
    try:
        _permit(lab)
        gateway = _gateway(lab)
        with pytest.raises(ProviderError) as missing:
            _consent(lab, mapping={})
        with pytest.raises(ProviderError) as flag_only:
            _consent(lab, mapping={"OPENAI_REMOTE_ENABLED": "1", "OPENAI_API_KEY": KEY}, phrase="no")
        with pytest.raises(ProviderError) as quiet:
            _consent(lab, interactive=False)
        assert missing.value.reason == "credential_absent"
        assert flag_only.value.reason == quiet.value.reason == "confirmation_required"
        forged = object.__new__(OperationalEgressConsent)
        with pytest.raises(ProviderError) as denied:
            _execute(gateway, lab, forged)
        assert denied.value.reason == "egress_blocked" and _status(lab) == []
        assert KEY not in repr(forged)
    finally:
        lab.close()


def test_invalid_principal_resource_budget_and_unknown_permit_make_no_call(tmp_path):
    lab = _ready(tmp_path)
    try:
        _permit(lab)
        gateway = _gateway(lab)
        other = lab.issuer.issue("ORG-A", "executor", principal_id="other-principal")
        wrong_principal = _consent(lab, principal="other-principal", client=_mock(_http(200, _body()))[0])
        with pytest.raises(ProviderError) as principal:
            _execute(gateway, lab, wrong_principal, access=other)
        wrong_resource = _consent(lab, resource="other-resource")
        with pytest.raises(ProviderError) as resource:
            _execute(gateway, lab, wrong_resource, resource="other-resource")
        with pytest.raises(ProviderError) as budget:
            _execute(gateway, lab, _consent(lab), budget=5000)
        with pytest.raises(ProviderError) as unknown:
            _execute(gateway, lab, _consent(lab, "missing-permit"), "missing-permit")
        assert principal.value.reason == resource.value.reason == "scope_mismatch"
        assert budget.value.reason == "budget_exceeded" and unknown.value.reason == "not_granted"
        assert _status(lab) == [] and wrong_principal.requests_sent == 0
    finally:
        lab.close()


def test_revoked_and_expired_permits_do_not_send(tmp_path):
    lab = _ready(tmp_path)
    try:
        _permit(lab, "egress-revoked")
        lab.ledger.revoke_remote_authorization(lab.admin["ORG-A"], "egress-revoked", "operator_revoked")
        now = lab.clock()
        _permit(
            lab, "egress-expired", valid_from=now - timedelta(minutes=10),
            expires_at=now - timedelta(minutes=1))
        gateway = _gateway(lab)
        with pytest.raises(ProviderError) as revoked:
            _execute(gateway, lab, _consent(lab, "egress-revoked"), "egress-revoked")
        with pytest.raises(ProviderError) as expired:
            _execute(gateway, lab, _consent(lab, "egress-expired"), "egress-expired")
        assert revoked.value.reason == "revoked" and expired.value.reason == "authorization_expired"
        assert _status(lab) == []
    finally:
        lab.close()


def test_a_confirmed_send_records_estimated_cost_and_consumes_once(tmp_path):
    lab = _ready(tmp_path)
    try:
        _permit(lab)
        client, requests = _mock(_http(200, _body(json.dumps(_observation()))))
        consent = _consent(lab, client=client)
        result = _execute(_gateway(lab), lab, consent)
        assert result.accepted is True and result.input_tokens == 32 and result.output_tokens == 16
        assert result.reserved_microusd == openai_reservation()
        assert result.estimated_microusd == estimate_microusd(32, 16, ceiling=False)
        assert result.cost_exact is False and result.cost_kind == "estimated"
        assert result.provider_request_id == "resp_test" and result.response_status == "completed"
        assert consent.requests_sent == 1 and len(requests) == 1 and _status(lab) == ["consumed"]
        again = _consent(lab, client=_mock(_http(200, _body()))[0])
        with pytest.raises(ProviderError) as replay:
            _execute(_gateway(lab), lab, again)
        assert replay.value.reason == "replay_denied" and again.requests_sent == 0
        other = lab.issuer.issue("ORG-A", "executor", principal_id="other-principal")
        stranger = _consent(lab, principal="other-principal", client=_mock(_http(200, _body()))[0])
        with pytest.raises(ProviderError) as denied:
            _execute(_gateway(lab), lab, stranger, access=other)
        same_name = lab.issuer.issue("ORG-A", "executor")
        repeat = _consent(lab, client=_mock(_http(200, _body()))[0])
        with pytest.raises(ProviderError) as reused:
            _execute(_gateway(lab), lab, repeat, access=same_name)
        assert denied.value.reason == "scope_mismatch" and stranger.requests_sent == 0
        assert reused.value.reason == "replay_denied" and repeat.requests_sent == 0
        assert _status(lab) == ["consumed"]
        assert KEY not in repr(consent) and KEY not in repr(result)
        root, issuer, clock = lab.ledger.root, lab.issuer, lab.clock
        lab.ledger.close()
        from app.enterprise_ai_processing.sqlite_ledger import SQLiteExecutionLedger
        from app.enterprise_ai_processing.durable_resolver import LedgerDurableAuthorization
        from app.model_gateway.gateway import NeutralModelGateway
        reopened = SQLiteExecutionLedger(root, issuer, clock)
        try:
            restarted = NeutralModelGateway(resolver=LedgerDurableAuthorization(reopened))
            fresh = lab.issuer.issue("ORG-A", "executor")
            restarted_consent = _consent(lab, client=_mock(_http(200, _body()))[0])
            with pytest.raises(ProviderError) as after:
                restarted.execute(
                    fresh, "egress-a", 1000, RESOURCE, DEPLOYMENT, egress_consent=restarted_consent)
            assert after.value.reason == "replay_denied" and restarted_consent.requests_sent == 0
        finally:
            reopened.close()
    finally:
        lab.close()


def test_timeout_http_and_invalid_output_keep_the_held_row(tmp_path):
    lab = _ready(tmp_path)
    try:
        _permit(lab, "egress-timeout")
        def timeout(request):
            raise httpx2.TimeoutException("slow")
        client, requests = _mock(timeout)
        consent = _consent(lab, "egress-timeout", client=client)
        with pytest.raises(ProviderError) as timed:
            _execute(_gateway(lab), lab, consent, "egress-timeout")
        assert timed.value.reason == "timeout" and consent.requests_sent == 1 and len(requests) == 1
        assert _status(lab) == ["held"] and KEY not in str(timed.value)
        with pytest.raises(ProviderError) as replay:
            _execute(_gateway(lab), lab, _consent(lab, "egress-timeout"), "egress-timeout")
        assert replay.value.reason == "replay_denied"
        lab.ledger.revoke_remote_authorization(lab.admin["ORG-A"], "egress-timeout", "operator_revoked")

        _permit(lab, "egress-http")
        client, requests = _mock(_http(500, {"error": {"message": KEY, "type": "server_error"}}))
        failed = _consent(lab, "egress-http", client=client)
        with pytest.raises(ProviderError) as http:
            _execute(_gateway(lab), lab, failed, "egress-http")
        assert http.value.reason == "remote_unavailable" and failed.requests_sent == 1
        assert KEY not in str(http.value) and "held" in _status(lab)
        lab.ledger.revoke_remote_authorization(lab.admin["ORG-A"], "egress-http", "operator_revoked")

        _permit(lab, "egress-bad")
        incomplete = _body(json.dumps(_observation()))
        incomplete["status"] = "incomplete"
        client, requests = _mock(_http(200, incomplete))
        bad = _consent(lab, "egress-bad", client=client)
        with pytest.raises(ProviderError) as invalid:
            _execute(_gateway(lab), lab, bad, "egress-bad")
        assert invalid.value.reason == "incomplete_output" and bad.requests_sent == 1
        assert _status(lab).count("held") == 3
    finally:
        lab.close()


def test_audit_failure_rolls_back_before_any_send(tmp_path):
    lab = _ready(tmp_path)
    try:
        _permit(lab, "egress-audit")
        def fault(stage):
            if stage == "audit_remote_authorization_evaluated":
                raise OSError("disk")
        lab.ledger._fault = fault
        consent = _consent(lab, "egress-audit", client=_mock(_http(200, _body()))[0])
        with pytest.raises(ProviderError) as failed:
            _execute(_gateway(lab), lab, consent, "egress-audit")
        assert failed.value.reason == "storage_unavailable"
        assert consent.requests_sent == 0 and _status(lab) == []
    finally:
        lab.close()


def test_two_gateways_send_once(tmp_path):
    lab = _ready(tmp_path)
    try:
        _permit(lab, "egress-race")
        outcomes, calls = [], []
        barrier = threading.Barrier(2)

        def attempt():
            client, requests = _mock(_http(200, _body(json.dumps(_observation()))))
            consent = _consent(lab, "egress-race", client=client)
            barrier.wait()
            try:
                outcomes.append(_execute(_gateway(lab), lab, consent, "egress-race").accepted)
            except ProviderError as error:
                outcomes.append(error.reason)
            calls.append(len(requests))

        threads = [threading.Thread(target=attempt) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert outcomes.count(True) == 1 and outcomes.count("replay_denied") == 1
        assert sum(calls) == 1 and _status(lab) == ["consumed"]
    finally:
        lab.close()


def test_a_bare_dispatch_cannot_skip_the_grant():
    from app.enterprise_llm_providers.transport import dispatch_authorized
    with pytest.raises(ProviderError) as skipped:
        dispatch_authorized(object(), {"model": "gpt-6-luna"}, 15)
    assert skipped.value.reason == "egress_blocked"


def test_public_transports_and_c03_stay_closed(caplog):
    caplog.set_level(logging.DEBUG)
    settings = ProviderSettings(True, "gpt-6-luna", 15, 256, 2048, 1000, 5_000_000, KEY)
    with pytest.raises(ProviderError) as openai_blocked:
        OpenAISDKTransport(KEY).send(build_payload(FIXED_DOCUMENT, settings), 15)
    gemini_settings = GeminiSettings(True, "gemini-3.5-flash-lite", 15, 128, 2048, 1000, "test-gemini-marker")
    generation = build_generation(FIXED_DOCUMENT, gemini_settings)
    with pytest.raises(ProviderError) as gemini_blocked:
        GeminiSDKTransport("test-gemini-marker").send(generation, 15)
    assert openai_blocked.value.reason == gemini_blocked.value.reason == "egress_blocked"
    assert live_egress_enabled() is False and KEY not in caplog.text
    enterprise = (PACKAGE / "enterprise_ai_processing" / "gateway.py").read_text(encoding="utf-8")
    agent = (PACKAGE / "model_gateway" / "agent.py").read_text(encoding="utf-8")
    tree = ast.parse(agent)
    imported = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    assert "FakeEnterpriseModel" in enterprise and "openai" not in imported
    assert FakeEnterpriseModel is not None


def test_smoke_command_stops_before_a_client(tmp_path):
    with pytest.raises(ProviderError) as quiet:
        egress_run(__import__("io").StringIO(PHRASE + "\n"), {"LOCALAPPDATA": str(tmp_path)})
    class _TTY(__import__("io").StringIO):
        def isatty(self):
            return True
    with pytest.raises(ProviderError) as wrong:
        egress_run(_TTY("no\n"), {"LOCALAPPDATA": str(tmp_path), "OPENAI_API_KEY": KEY})
    with pytest.raises(ProviderError) as missing:
        egress_run(_TTY(PHRASE + "\n"), {"LOCALAPPDATA": str(tmp_path)})
    with pytest.raises(ProviderError) as proxied:
        egress_run(_TTY(PHRASE + "\n"), {
            "LOCALAPPDATA": str(tmp_path), "OPENAI_API_KEY": KEY, "HTTPS_PROXY": "http://127.0.0.1:9"})
    assert quiet.value.reason == wrong.value.reason == "confirmation_required"
    assert missing.value.reason == "credential_absent" and proxied.value.reason == "environment_redirect"
    assert KEY not in str(missing.value)
