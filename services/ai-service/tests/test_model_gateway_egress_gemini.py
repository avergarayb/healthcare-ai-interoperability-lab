"""Controlled Gemini egress. The network mock never leaves the process."""
import json
import socket
import sqlite3
import threading
from datetime import timedelta
from io import StringIO

import httpx
import pytest

from app.enterprise_ai_processing.remote_authorization import RESERVATION_MICROUSD
from app.enterprise_llm_providers.errors import ProviderError
from app.enterprise_llm_providers.egress_gemini_once import run as gemini_run
from app.enterprise_llm_providers.gemini_configuration import GeminiSettings
from app.enterprise_llm_providers.gemini_pricing import STANDARD_INPUT, STANDARD_OUTPUT, estimate_microusd
from app.enterprise_llm_providers.gemini_request import build_generation
from app.enterprise_llm_providers.gemini_transport import GeminiSDKTransport, dispatch_authorized
from app.enterprise_llm_providers.smoke import FIXED_DOCUMENT
from app.enterprise_llm_providers.transport import live_egress_enabled
from app.model_gateway.egress import OperationalEgressConsent
from app.model_gateway.egress_gemini import PHRASE, OperationalGeminiConsent
from app.model_gateway.sdk_bridge import gemini_operational_reservation, gemini_reservation
from tests.test_model_gateway_durable_authorization import RESOURCE, _gateway, _ready, _register


KEY = "test-gemini-marker"
DEPLOYMENT = "gemini-sdk-a"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("provider socket forbidden")

    monkeypatch.setattr(socket, "socket", forbidden)


def _permit(lab, authorization_id="egress-g", **overrides):
    values = dict(
        authorization_id=authorization_id, deployment_id=DEPLOYMENT, provider_id="gemini",
        model_id="gemini-3.5-flash-lite", budget_ceiling_microusd=1000, resource_id=RESOURCE)
    values.update(overrides)
    return _register(lab, **values)


def _consent(lab, authorization_id="egress-g", client=None, principal=None, resource=RESOURCE,
             phrase=PHRASE, interactive=True, mapping=None):
    access = lab.executor["ORG-A"]
    body = {"GEMINI_API_KEY": KEY} if mapping is None else mapping
    return OperationalGeminiConsent.issue(
        body, authorization_id=authorization_id, deployment_id=DEPLOYMENT, organization_id="ORG-A",
        principal_id=access.principal_id if principal is None else principal, resource_id=resource,
        phrase=phrase, interactive=interactive, http_client=None if client is None else client)


def _mock(handler):
    requests = []

    def wrapped(request):
        requests.append(request)
        return handler(request)

    client = httpx.Client(transport=httpx.MockTransport(wrapped))
    return client, requests


def _observation():
    encoded = FIXED_DOCUMENT.encode("utf-8")
    return {
        "question_id": "vacation-days-v1", "evidence_found": True, "proposed_days": 20,
        "proposed_months": 12, "source_excerpt": FIXED_DOCUMENT, "evidence_start": 0,
        "evidence_end": len(encoded), "refusal_or_insufficient": False,
    }


def _body(text=None):
    if text is None:
        text = json.dumps(_observation())
    return {
        "responseId": "resp_gemini_test",
        "modelVersion": "gemini-3.5-flash-lite",
        "candidates": [{"content": {"role": "model", "parts": [{"text": text}]}, "finishReason": "STOP"}],
        "usageMetadata": {"promptTokenCount": 40, "candidatesTokenCount": 16, "thoughtsTokenCount": 0},
    }


def _http(status, payload):
    def handler(request):
        return httpx.Response(status, json=payload, request=request)
    return handler


def _execute(gateway, lab, consent, authorization_id="egress-g", budget=1000, resource=RESOURCE, access=None):
    chosen = lab.executor["ORG-A"] if access is None else access
    return gateway.execute(
        chosen, authorization_id, budget, resource, DEPLOYMENT, egress_consent=consent)


def _status(lab):
    with sqlite3.connect(lab.ledger.path) as connection:
        rows = connection.execute("SELECT status FROM aip_remote_execution_reservation").fetchall()
    return [row[0] for row in rows]


def test_catalog_keeps_the_rates_and_prices_256_output_under_the_ceiling():
    assert STANDARD_INPUT == 300_000 and STANDARD_OUTPUT == 2_500_000
    assert gemini_reservation() == 657
    assert gemini_operational_reservation() == 977
    assert RESERVATION_MICROUSD["gemini-sdk-a"] == 977
    assert RESERVATION_MICROUSD["gemini-offline-a"] == 470
    assert RESERVATION_MICROUSD["openai-sdk-a"] == 303
    assert 977 <= 1000


def test_default_egress_stays_closed_and_openai_consent_cannot_spend_gemini(tmp_path):
    lab = _ready(tmp_path)
    try:
        _permit(lab, "egress-off")
        with pytest.raises(ProviderError) as blocked:
            _gateway(lab).execute(lab.executor["ORG-A"], "egress-off", 1000, RESOURCE, DEPLOYMENT)
        assert blocked.value.reason == "remote_disabled" and _status(lab) == ["held"]
        assert live_egress_enabled() is False
        generation = build_generation(
            FIXED_DOCUMENT, GeminiSettings(True, "gemini-3.5-flash-lite", 15, 128, 2048, 1000, KEY))
        with pytest.raises(ProviderError) as public:
            GeminiSDKTransport(KEY).send(generation, 15)
        assert public.value.reason == "egress_blocked"
        openai = OperationalEgressConsent.issue(
            {"OPENAI_API_KEY": "sk-lab-not-a-real-key"}, authorization_id="egress-off",
            deployment_id="openai-sdk-a", organization_id="ORG-A",
            principal_id=lab.executor["ORG-A"].principal_id, resource_id=RESOURCE,
            phrase="CONFIRMO EGRESS-001 UNA SOLICITUD openai gpt-6-luna vacation-days-v1 DATOS SINTETICOS SIN REINTENTO",
            interactive=True, max_output_tokens=256)
        with pytest.raises(ProviderError) as crossed:
            _execute(_gateway(lab), lab, openai, "egress-off")
        assert crossed.value.reason == "egress_blocked" and openai.requests_sent == 0
        assert _status(lab) == ["held"]
    finally:
        lab.close()


def test_missing_key_wrong_phrase_and_a_flag_do_not_hold_a_row(tmp_path):
    lab = _ready(tmp_path)
    try:
        for mapping, phrase, interactive in (
            ({}, PHRASE, True),
            ({"GEMINI_API_KEY": KEY}, "no", True),
            ({"GEMINI_API_KEY": KEY, "GEMINI_REMOTE_ENABLED": "1"}, PHRASE, False),
        ):
            with pytest.raises(ProviderError):
                _consent(lab, mapping=mapping, phrase=phrase, interactive=interactive)
        assert _status(lab) == []
    finally:
        lab.close()


def test_wrong_principal_resource_budget_and_model_send_nothing(tmp_path):
    lab = _ready(tmp_path)
    try:
        _permit(lab)
        other = lab.issuer.issue("ORG-A", "executor", principal_id="other-principal")
        stranger = _consent(lab, principal="other-principal", client=_mock(_http(200, _body()))[0])
        with pytest.raises(ProviderError) as denied:
            _execute(_gateway(lab), lab, stranger, access=other)
        with pytest.raises(ProviderError) as resource:
            _execute(_gateway(lab), lab, _consent(lab, resource="other-resource"), resource="other-resource")
        with pytest.raises(ProviderError) as budget:
            _execute(_gateway(lab), lab, _consent(lab), budget=500)
        with pytest.raises(ProviderError) as model:
            OperationalGeminiConsent.issue(
                {"GEMINI_API_KEY": KEY}, authorization_id="egress-g", deployment_id=DEPLOYMENT,
                organization_id="ORG-A", principal_id="synthetic-executor", resource_id=RESOURCE,
                phrase=PHRASE, interactive=True, model_id="gemini-2.0-flash")
        assert denied.value.reason == resource.value.reason == "scope_mismatch"
        assert budget.value.reason == "budget_exceeded" and model.value.reason == "model_denied"
        assert stranger.requests_sent == 0 and _status(lab) == []
    finally:
        lab.close()


def test_revoked_and_expired_permits_send_nothing(tmp_path):
    lab = _ready(tmp_path)
    try:
        _permit(lab, "egress-revoked")
        lab.ledger.revoke_remote_authorization(lab.admin["ORG-A"], "egress-revoked", "operator_revoked")
        consent = _consent(lab, "egress-revoked", client=_mock(_http(200, _body()))[0])
        with pytest.raises(ProviderError) as revoked:
            _execute(_gateway(lab), lab, consent, "egress-revoked")
        _permit(lab, "egress-expired", expires_at=lab.clock() - timedelta(seconds=1))
        expired = _consent(lab, "egress-expired", client=_mock(_http(200, _body()))[0])
        with pytest.raises(ProviderError) as old:
            _execute(_gateway(lab), lab, expired, "egress-expired")
        assert revoked.value.reason == "revoked" and old.value.reason == "authorization_expired"
        assert consent.requests_sent == expired.requests_sent == 0 and _status(lab) == []
    finally:
        lab.close()


def test_a_consent_cannot_spend_a_replacement_permit(tmp_path):
    lab = _ready(tmp_path)
    try:
        _permit(lab, "egress-a")
        consent = _consent(lab, "egress-a", client=_mock(_http(200, _body()))[0])
        lab.ledger.revoke_remote_authorization(lab.admin["ORG-A"], "egress-a", "operator_revoked")
        _permit(lab, "egress-b")
        with pytest.raises(ProviderError) as caught:
            _execute(_gateway(lab), lab, consent, "egress-b")
        assert caught.value.reason == "egress_blocked" and consent.requests_sent == 0
        assert _status(lab) == []
    finally:
        lab.close()


def test_a_confirmed_send_records_estimated_cost_and_blocks_another_caller(tmp_path):
    lab = _ready(tmp_path)
    try:
        _permit(lab)
        client, requests = _mock(_http(200, _body()))
        consent = _consent(lab, client=client)
        result = _execute(_gateway(lab), lab, consent)
        assert result.accepted is True and result.input_tokens == 40 and result.output_tokens == 16
        assert result.reserved_microusd == gemini_operational_reservation() == 977
        assert result.estimated_microusd == estimate_microusd(40, 16)
        assert result.cost_exact is False and result.cost_kind == "estimated"
        assert result.provider_request_id == "resp_gemini_test" and result.response_status == "completed"
        assert consent.requests_sent == 1 and len(requests) == 1 and _status(lab) == ["consumed"]
        assert KEY not in repr(consent) and KEY not in repr(result)
        other = lab.issuer.issue("ORG-A", "executor", principal_id="other-principal")
        stranger = _consent(lab, principal="other-principal", client=_mock(_http(200, _body()))[0])
        with pytest.raises(ProviderError) as denied:
            _execute(_gateway(lab), lab, stranger, access=other)
        same = lab.issuer.issue("ORG-A", "executor")
        repeat = _consent(lab, client=_mock(_http(200, _body()))[0])
        with pytest.raises(ProviderError) as reused:
            _execute(_gateway(lab), lab, repeat, access=same)
        assert denied.value.reason == "scope_mismatch" and reused.value.reason == "replay_denied"
        assert stranger.requests_sent == repeat.requests_sent == 0 and _status(lab) == ["consumed"]
        root, issuer, clock = lab.ledger.root, lab.issuer, lab.clock
        lab.ledger.close()
        from app.enterprise_ai_processing.sqlite_ledger import SQLiteExecutionLedger
        from app.enterprise_ai_processing.durable_resolver import LedgerDurableAuthorization
        from app.model_gateway.gateway import NeutralModelGateway
        reopened = SQLiteExecutionLedger(root, issuer, clock)
        try:
            restarted = NeutralModelGateway(resolver=LedgerDurableAuthorization(reopened))
            fresh = lab.issuer.issue("ORG-A", "executor")
            again = _consent(lab, client=_mock(_http(200, _body()))[0])
            with pytest.raises(ProviderError) as after:
                restarted.execute(fresh, "egress-g", 1000, RESOURCE, DEPLOYMENT, egress_consent=again)
            assert after.value.reason == "replay_denied" and again.requests_sent == 0
        finally:
            reopened.close()
    finally:
        lab.close()


def test_timeout_http_and_invalid_output_keep_the_held_row(tmp_path):
    lab = _ready(tmp_path)
    try:
        def timeout(request):
            raise httpx.ReadTimeout("slow")

        cases = (
            ("egress-timeout", timeout, "timeout"),
            ("egress-http", _http(500, {"error": {"message": "down", "code": 500}}), "remote_unavailable"),
            ("egress-auth", _http(401, {"error": {"message": "denied", "code": 401}}), "credential_rejected"),
            ("egress-model", _http(404, {"error": {"message": "missing", "code": 404}}), "model_denied"),
            ("egress-quota", _http(429, {"error": {"message": "quota", "code": 429}}), "rate_limited"),
            ("egress-bad", _http(200, _body("not-json")), "invalid_output"),
        )
        for authorization_id, handler, reason in cases:
            _permit(lab, authorization_id)
            client, requests = _mock(handler)
            consent = _consent(lab, authorization_id, client=client)
            with pytest.raises(ProviderError) as caught:
                _execute(_gateway(lab), lab, consent, authorization_id)
            assert caught.value.reason == reason and KEY not in str(caught.value)
            assert consent.requests_sent == 1 and len(requests) == 1
            lab.ledger.revoke_remote_authorization(lab.admin["ORG-A"], authorization_id, "operator_revoked")
        assert _status(lab).count("held") == len(cases)
    finally:
        lab.close()


def test_audit_failure_and_two_gateways_send_once(tmp_path):
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
        assert failed.value.reason == "storage_unavailable" and consent.requests_sent == 0
        lab.ledger._fault = lambda stage: None
        lab.ledger.revoke_remote_authorization(lab.admin["ORG-A"], "egress-audit", "operator_revoked")
        _permit(lab, "egress-race")
        gateways = (_gateway(lab), _gateway(lab))
        consents = (
            _consent(lab, "egress-race", client=_mock(_http(200, _body()))[0]),
            _consent(lab, "egress-race", client=_mock(_http(200, _body()))[0]),
        )
        outcomes = []

        def run(gateway, consent):
            try:
                outcomes.append(_execute(gateway, lab, consent, "egress-race") is not None)
            except ProviderError as error:
                outcomes.append(error.reason)

        threads = [threading.Thread(target=run, args=pair) for pair in zip(gateways, consents)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert outcomes.count(True) == 1 and outcomes.count("replay_denied") == 1
        assert sum(item.requests_sent for item in consents) == 1
        assert _status(lab).count("consumed") == 1
    finally:
        lab.close()


def test_a_bare_dispatch_and_the_smoke_command_do_not_send(tmp_path):
    with pytest.raises(ProviderError) as skipped:
        dispatch_authorized(object(), {"model": "gemini-3.5-flash-lite"}, None)
    assert skipped.value.reason == "egress_blocked"

    class _TTY(StringIO):
        def isatty(self):
            return True

    with pytest.raises(ProviderError) as blocked:
        gemini_run(_TTY("no\n"), {"LOCALAPPDATA": str(tmp_path), "GEMINI_API_KEY": KEY})
    with pytest.raises(ProviderError) as missing:
        gemini_run(_TTY(PHRASE + "\n"), {"LOCALAPPDATA": str(tmp_path)})
    with pytest.raises(ProviderError) as proxied:
        gemini_run(_TTY(PHRASE + "\n"), {
            "LOCALAPPDATA": str(tmp_path), "GEMINI_API_KEY": KEY, "HTTPS_PROXY": "http://127.0.0.1:9"})
    assert blocked.value.reason == "confirmation_required"
    assert missing.value.reason == "credential_absent" and proxied.value.reason == "environment_redirect"
    assert KEY not in str(blocked.value)
