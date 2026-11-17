"""External FHIR summary through the neutral gateway. The provider socket stays closed."""
import json
import socket
import sqlite3

import httpx
import pytest

from app.clinical_lab_summary.http import _detail
from app.clinical_lab_summary.review import (
    IamReviewer, ReviewError, iam_principal_id, queue_summary, read_review, read_status,
    review_organization,
)
from app.enterprise_ai_processing.execution_types import ExecutionError
from app.enterprise_ai_processing.remote_authorization import (
    CLINICAL_OPERATION_ID, CLINICAL_POLICY_REF, EXTERNAL_OPERATION_ID, EXTERNAL_POLICY_REF,
)
from app.enterprise_llm_providers.errors import ProviderError
from app.external_fhir.consent import PHRASE, OperationalExternalConsent
from app.external_fhir.context import minimize_envelope
from app.external_fhir.graph import ExternalFhirGraph
from app.external_fhir.policy import (
    AUTHORIZATION_ID, DEPLOYMENT_ID, OPERATION_ID, ORGANIZATION_ID, PATIENT_ID, SOURCE,
    request_real_provider_send,
)
from tests.test_external_fhir import IDENTIFIER_SYSTEM, _envelope
from tests.test_lab_review_iam import ORIGIN, _client, _key, _login
from tests.test_lab_summary import _gemini
from tests.test_model_gateway_durable_authorization import _gateway, _ready, _register
from tests.test_model_gateway_egress_gemini import KEY, _body


SUMMARY = json.dumps({
    "kind": OPERATION_ID,
    "review": "pending_human_review",
    "statements": [{
        "text": "HDL 69.3 mg/dL",
        "sources": [{"source": SOURCE, "resourceType": "Observation", "id": "obs-verified"}],
    }],
})
OTHER_REVIEW = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb1"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("provider socket forbidden")

    monkeypatch.setattr(socket, "socket", forbidden)


def test_intercepted_gateway_queues_pending_review(tmp_path):
    lab = _laboratory(tmp_path)
    try:
        _permit(lab)
        federation, reads = _federation()
        gemini, sends = _gemini(lambda request: httpx.Response(200, json=_body(SUMMARY), request=request))
        consent = _consent(lab, gemini)
        graph = ExternalFhirGraph(_gateway(lab), federation, lambda _event: None, tmp_path / "review.sqlite3")
        state = graph.invoke(lab.executor[ORGANIZATION_ID], AUTHORIZATION_ID, 1000, PATIENT_ID, consent)
        assert state["phase"] == "PENDING_REVIEW"
        assert state["reason"] == "pending_human_review"
        assert state["review_status"] == "pending"
        assert state["requests_sent"] == 1
        assert state["response_status"] == "intercepted"
        assert graph.model_calls == 1
        assert len(sends) == 1 and len(reads) == 1
        assert reads[0].url.host != "r4.smarthealthit.org"
        assert sends[0].url.host == "generativelanguage.googleapis.com"
        assert read_status(tmp_path / "review.sqlite3", state["review_id"]) == "pending"
        assert review_organization(tmp_path / "review.sqlite3", state["review_id"]) == ORGANIZATION_ID
        receipt = json.loads((tmp_path / "receipt.json").read_text(encoding="utf-8"))
        assert receipt["phase"] == "intercepted"
        assert receipt["provider"] == "gemini"
        assert receipt["model"] == "gemini-3.5-flash-lite"
        assert receipt["operation_id"] == OPERATION_ID
        assert "AIza" not in json.dumps(receipt)
        case = read_review(tmp_path / "review.sqlite3", state["review_id"])
        case["organization_id"] = ORGANIZATION_ID
        page = _detail(case, _Page())
        assert "interceptado" in page
        assert SOURCE in page and "obs-verified" in page and "pending" in page
        assert ORGANIZATION_ID in page
        again = graph.invoke(lab.executor[ORGANIZATION_ID], AUTHORIZATION_ID, 1000, PATIENT_ID, consent)
        assert again["reason"] == "replay_denied" and len(sends) == 1
        assert _reservation(lab) == ["consumed"]
    finally:
        lab.close()


def test_missing_other_and_spent_permits_do_not_send(tmp_path):
    lab = _laboratory(tmp_path)
    try:
        federation, reads = _federation()
        gemini, sends = _gemini(lambda request: httpx.Response(200, json=_body(SUMMARY), request=request))
        missing = ExternalFhirGraph(_gateway(lab), federation, lambda _event: None, tmp_path / "missing.sqlite3")
        state = missing.invoke(
            lab.executor[ORGANIZATION_ID], AUTHORIZATION_ID, 1000, PATIENT_ID, _consent(lab, gemini))
        assert state["reason"] == "not_granted" and sends == [] and not (tmp_path / "missing.sqlite3").exists()

        _permit(lab, operation_id=CLINICAL_OPERATION_ID, policy_ref=CLINICAL_POLICY_REF)
        other = ExternalFhirGraph(_gateway(lab), federation, lambda _event: None, tmp_path / "other.sqlite3")
        state = other.invoke(
            lab.executor[ORGANIZATION_ID], AUTHORIZATION_ID, 1000, PATIENT_ID, _consent(lab, gemini))
        assert state["reason"] == "operation_denied" and sends == []
    finally:
        lab.close()
    (tmp_path / "spent-lab").mkdir()
    lab = _laboratory(tmp_path / "spent-lab")
    try:
        _permit(lab)
        federation, reads = _federation()
        gemini, sends = _gemini(lambda request: httpx.Response(200, json=_body(SUMMARY), request=request))
        spent = ExternalFhirGraph(_gateway(lab), federation, lambda _event: None, tmp_path / "spent.sqlite3")
        done = spent.invoke(
            lab.executor[ORGANIZATION_ID], AUTHORIZATION_ID, 1000, PATIENT_ID, _consent(lab, gemini))
        assert done["phase"] == "PENDING_REVIEW" and len(sends) == 1
        restarted = ExternalFhirGraph(_gateway(lab), federation, lambda _event: None, tmp_path / "spent.sqlite3")
        again = restarted.invoke(
            lab.executor[ORGANIZATION_ID], AUTHORIZATION_ID, 1000, PATIENT_ID, _consent(lab, gemini))
        assert again["reason"] == "replay_denied" and again["requests_sent"] == 0 and len(sends) == 1
        assert reads
    finally:
        lab.close()


def test_budget_missing_credential_and_closed_send_do_not_call(tmp_path, monkeypatch):
    lab = _laboratory(tmp_path)
    try:
        _permit(lab)
        federation, _reads = _federation()
        gemini, sends = _gemini(lambda request: httpx.Response(200, json=_body(SUMMARY), request=request))
        low = ExternalFhirGraph(_gateway(lab), federation, lambda _event: None, tmp_path / "low.sqlite3")
        state = low.invoke(
            lab.executor[ORGANIZATION_ID], AUTHORIZATION_ID, 100, PATIENT_ID, _consent(lab, gemini))
        assert state["reason"] == "budget_exceeded" and sends == []
        monkeypatch.setenv("GEMINI_API_KEY", KEY)
        try:
            _consent(lab, gemini, mapping={})
        except ProviderError as error:
            assert error.reason == "credential_absent"
        else:
            raise AssertionError("credential")
        try:
            _consent(lab, None)
        except ProviderError as error:
            assert error.reason == "provider_send_blocked"
        else:
            raise AssertionError("live")
        try:
            request_real_provider_send()
        except ProviderError as error:
            assert error.reason == "provider_send_blocked"
        else:
            raise AssertionError("armed")
        closed = ExternalFhirGraph(None, federation, lambda _event: None, tmp_path / "closed.sqlite3")
        denied = closed.invoke(lab.executor[ORGANIZATION_ID], AUTHORIZATION_ID, 1000, PATIENT_ID, None)
        assert denied["reason"] == "model_denied" and not (tmp_path / "closed.sqlite3").exists()
        partial_payload = _envelope(include_unverified=False)
        partial_payload["status"] = "partial"
        partial_client, partial_reads = _federation(partial_payload)
        partial = ExternalFhirGraph(
            _gateway(lab), partial_client, lambda _event: None, tmp_path / "partial.sqlite3")
        incomplete = partial.invoke(
            lab.executor[ORGANIZATION_ID], AUTHORIZATION_ID, 1000, PATIENT_ID, _consent(lab, gemini))
        assert incomplete["reason"] == "context_incomplete" and partial_reads and sends == []
        assert not (tmp_path / "partial.sqlite3").exists()
    finally:
        lab.close()


def test_invalid_and_invented_output_are_not_queued(tmp_path):
    lab = _laboratory(tmp_path)
    try:
        _permit(lab)
        invented = json.dumps({
            "kind": OPERATION_ID,
            "review": "pending_human_review",
            "statements": [{
                "text": "HDL 69.3 mg/dL",
                "sources": [{"source": SOURCE, "resourceType": "Observation", "id": "obs-invented"}],
            }],
        })
        for name, text in (("invalid", "not-json"), ("invented", invented)):
            federation, _reads = _federation()
            gemini, sends = _gemini(lambda request, payload=text: httpx.Response(
                200, json=_body(payload), request=request))
            graph = ExternalFhirGraph(
                _gateway(lab), federation, lambda _event: None, tmp_path / (name + ".sqlite3"))
            state = graph.invoke(
                lab.executor[ORGANIZATION_ID], AUTHORIZATION_ID, 1000, PATIENT_ID, _consent(lab, gemini))
            assert state["phase"] == "FAILED" and state["reason"] == "invalid_output"
            assert not (tmp_path / (name + ".sqlite3")).exists()
            assert len(sends) == 1
            lab.close()
            root = tmp_path / name
            root.mkdir()
            lab = _laboratory(root)
            _permit(lab)
    finally:
        lab.close()


def test_failure_after_reservation_is_not_retried(tmp_path):
    lab = _laboratory(tmp_path)
    try:
        _permit(lab)
        federation, _reads = _federation()
        gemini, sends = _gemini(lambda request: httpx.Response(500, json={"error": {"status": "INTERNAL"}}, request=request))
        graph = ExternalFhirGraph(_gateway(lab), federation, lambda _event: None, tmp_path / "failed.sqlite3")
        failed = graph.invoke(
            lab.executor[ORGANIZATION_ID], AUTHORIZATION_ID, 1000, PATIENT_ID, _consent(lab, gemini))
        assert failed["phase"] == "FAILED" and failed["requests_sent"] == 1
        assert not (tmp_path / "failed.sqlite3").exists()
        assert _reservation(lab) == ["held"]
        restarted = ExternalFhirGraph(_gateway(lab), federation, lambda _event: None, tmp_path / "failed.sqlite3")
        again = restarted.invoke(
            lab.executor[ORGANIZATION_ID], AUTHORIZATION_ID, 1000, PATIENT_ID, _consent(lab, gemini))
        assert again["reason"] == "replay_denied" and len(sends) == 1
    finally:
        lab.close()


def test_same_permit_cannot_execute_concurrently(tmp_path):
    lab = _laboratory(tmp_path)
    try:
        _permit(lab)
        chart = minimize_envelope(_envelope(include_unverified=False), PATIENT_ID)
        first = _gemini(lambda request: httpx.Response(200, json=_body(SUMMARY), request=request))
        second = _gemini(lambda request: httpx.Response(200, json=_body(SUMMARY), request=request))
        gateway = _gateway(lab)
        nested = []

        def before(summary):
            try:
                gateway.execute_external_summary(
                    lab.executor[ORGANIZATION_ID], AUTHORIZATION_ID, 1000, PATIENT_ID, DEPLOYMENT_ID,
                    chart, _consent(lab, second[0]), lambda _item: None)
            except ProviderError as error:
                nested.append(error.reason)
            else:
                nested.append("sent")

        result = gateway.execute_external_summary(
            lab.executor[ORGANIZATION_ID], AUTHORIZATION_ID, 1000, PATIENT_ID, DEPLOYMENT_ID,
            chart, _consent(lab, first[0]), before)
        assert result.summary["review"] == "pending_human_review"
        assert nested == ["replay_denied"]
        assert len(first[1]) == 1 and second[1] == []
    finally:
        lab.close()


def test_oidc_reviewer_is_limited_to_the_external_organization(tmp_path, monkeypatch):
    lab = _laboratory(tmp_path)
    try:
        _permit(lab)
        federation, _reads = _federation()
        gemini, sends = _gemini(lambda request: httpx.Response(200, json=_body(SUMMARY), request=request))
        graph = ExternalFhirGraph(_gateway(lab), federation, lambda _event: None, tmp_path / "review.sqlite3")
        state = graph.invoke(
            lab.executor[ORGANIZATION_ID], AUTHORIZATION_ID, 1000, PATIENT_ID, _consent(lab, gemini))
        review_id = state["review_id"]
        monkeypatch.undo()
        queue_summary(
            tmp_path / "review.sqlite3", OTHER_REVIEW, "other-org", "MHS-PAT-009",
            json.loads(SUMMARY))
        from app.clinical_lab_summary.review import assign_review_organization
        assign_review_organization(tmp_path / "review.sqlite3", OTHER_REVIEW, "org-lab-b")
        issuer = "http://127.0.0.1:18294/realms/lab-review-iam"
        try:
            IamReviewer(
                iam_principal_id(issuer, "auditor-ext"), issuer, "auditor-ext", ORGANIZATION_ID,
                "clinical-auditor", "session")
        except ReviewError as error:
            assert error.reason == "role_denied"
        else:
            raise AssertionError("auditor")
        extra = [
            {"sub": "reviewer-ext", "organization_id": ORGANIZATION_ID,
             "role": "clinical-reviewer", "display_name": "Reviewer External"},
            {"sub": "auditor-ext", "organization_id": ORGANIZATION_ID,
             "role": "clinical-auditor", "display_name": "Auditor External"},
        ]
        key = _key()
        auditor, issued, _settings = _client(tmp_path, key, "auditor-ext", extra)
        assert _login(auditor, issued).status_code == 303
        page = auditor.get("/lab-summaries/" + review_id)
        assert page.status_code == 200 and "interceptado" in page.text and PATIENT_ID in page.text
        assert OTHER_REVIEW not in page.text
        blocked = auditor.post(
            "/lab-summaries/" + review_id + "/decision",
            content=b"decision=approved&note=sintetica&csrf=not-the-token",
            headers={"content-type": "application/x-www-form-urlencoded", **ORIGIN})
        assert blocked.status_code == 403
        assert read_status(tmp_path / "review.sqlite3", review_id) == "pending"
        reviewer, issued, _settings = _client(tmp_path, key, "reviewer-ext", extra)
        assert _login(reviewer, issued).status_code == 303
        foreign = reviewer.get("/lab-summaries/" + OTHER_REVIEW)
        assert foreign.status_code == 403
        detail = reviewer.get("/lab-summaries/" + review_id)
        assert detail.status_code == 200
        assert OPERATION_ID in detail.text and SOURCE in detail.text and "pending" in detail.text
        csrf = detail.text.split('name="csrf" value="', 1)[1].split('"', 1)[0]
        missing = reviewer.post(
            "/lab-summaries/" + review_id + "/decision",
            content=b"decision=approved&note=sintetica",
            headers={"content-type": "application/x-www-form-urlencoded", **ORIGIN})
        assert missing.status_code == 422
        before = sqlite3.connect(tmp_path / "review.sqlite3").execute(
            "SELECT summary_json, status FROM lab_summary_review WHERE review_id=?",
            (review_id,)).fetchone()
        accepted = reviewer.post(
            "/lab-summaries/" + review_id + "/decision",
            content=("decision=approved&note=Cifra%20sintetica&csrf=" + csrf).encode(),
            headers={"content-type": "application/x-www-form-urlencoded", **ORIGIN},
            follow_redirects=False)
        assert accepted.status_code == 303
        again = reviewer.post(
            "/lab-summaries/" + review_id + "/decision",
            content=("decision=rejected&note=tarde&csrf=" + csrf).encode(),
            headers={"content-type": "application/x-www-form-urlencoded", **ORIGIN})
        assert again.status_code == 409
        current = sqlite3.connect(tmp_path / "review.sqlite3").execute(
            "SELECT summary_json, status FROM lab_summary_review WHERE review_id=?",
            (review_id,)).fetchone()
        assert current == before
        confirmed = reviewer.get("/lab-summaries/" + review_id)
        assert "reviewer-ext" in confirmed.text and "approved" in confirmed.text
        assert len(sends) == 1
    finally:
        lab.close()
        from app.main import app
        app.dependency_overrides.clear()


class _Page:
    mode = "development"
    permissions = frozenset()
    csrf = ""


def _laboratory(tmp_path):
    lab = _ready(tmp_path)
    try:
        lab.ledger.migrate_to_v6(lab.admin["ORG-A"])
        lab.ledger.migrate_to_v7(lab.admin["ORG-A"])
    except ExecutionError as error:
        if error.reason != "revision_conflict":
            raise
    lab.admin[ORGANIZATION_ID] = lab.issuer.issue(ORGANIZATION_ID)
    lab.executor[ORGANIZATION_ID] = lab.issuer.issue(ORGANIZATION_ID, "executor")
    return lab


def _permit(lab, **overrides):
    values = dict(
        authorization_id=AUTHORIZATION_ID, organization_id=ORGANIZATION_ID,
        deployment_id=DEPLOYMENT_ID, provider_id="gemini", model_id="gemini-3.5-flash-lite",
        resource_id=PATIENT_ID, budget_ceiling_microusd=1000,
        operation_id=EXTERNAL_OPERATION_ID, policy_ref=EXTERNAL_POLICY_REF,
        principal_id=lab.executor[ORGANIZATION_ID].principal_id)
    values.update(overrides)
    return _register(lab, **values)


def _consent(lab, http_client, mapping=None):
    access = lab.executor[ORGANIZATION_ID]
    return OperationalExternalConsent.issue(
        {"GEMINI_API_KEY": KEY} if mapping is None else mapping,
        authorization_id=AUTHORIZATION_ID, deployment_id=DEPLOYMENT_ID,
        organization_id=ORGANIZATION_ID, principal_id=access.principal_id,
        resource_id=PATIENT_ID, phrase=PHRASE, interactive=True, http_client=http_client)


def _federation(payload=None):
    from app.clinical_federation_client import ClinicalFederationClient

    reads = []
    body = _envelope(include_unverified=True) if payload is None else payload

    def handler(request):
        reads.append(request)
        return httpx.Response(200, json=body, request=request)

    federation = ClinicalFederationClient(
        "http://127.0.0.1:18281", "lab-token", organization_id="org-mini-his",
        patient_system_key="mini-his", patient_identifier_system=IDENTIFIER_SYSTEM,
        sources=(SOURCE,), http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    return federation, reads


def _reservation(lab):
    with sqlite3.connect(lab.ledger.path) as connection:
        return [row[0] for row in connection.execute(
            "SELECT status FROM aip_remote_execution_reservation")]
