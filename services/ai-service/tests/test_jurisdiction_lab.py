"""Peru and Spain share one graph, one gateway, and intercepted transport."""
import copy
import json
import socket

import httpx
import pytest

from app.clinical_federation_client import ClinicalFederationClient
from app.clinical_lab_summary.http import _detail
from app.clinical_lab_summary.review import (
    IamReviewer, ReviewError, iam_principal_id, read_review, read_status, reviews_for_organization,
)
from app.enterprise_ai_processing.remote_authorization import EXTERNAL_OPERATION_ID, EXTERNAL_POLICY_REF
from app.enterprise_llm_providers.errors import ProviderError
from app.jurisdiction_lab.consent import PHRASE, OperationalJurisdictionConsent
from app.jurisdiction_lab.context import minimize_envelope
from app.jurisdiction_lab.graph import JurisdictionLabGraph
from app.jurisdiction_lab.policy import request_real_provider_send
from app.jurisdiction_lab.profile import CALLER_ORGANIZATION, CALLER_SYSTEM, OPERATION_ID, PERU, SPAIN, require_profile
from tests.test_lab_summary import _gemini
from tests.test_model_gateway_durable_authorization import _gateway, _ready, _register
from tests.test_model_gateway_egress_gemini import KEY, _body


ISSUER = "http://127.0.0.1:18294/realms/lab-review-iam"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("provider socket forbidden")

    monkeypatch.setattr(socket, "socket", forbidden)


def test_profiles_are_closed():
    assert require_profile("pe-lab-demo-v1") is PERU
    assert require_profile("es-lab-demo-v1") is SPAIN
    with pytest.raises(ProviderError) as unknown:
        require_profile("clinic-x")
    assert unknown.value.reason == "profile_unknown"
    with pytest.raises(ProviderError) as missing:
        require_profile("pe-lab-demo-v9")
    assert missing.value.reason == "profile_version_unavailable"
    with pytest.raises(ProviderError) as blocked:
        request_real_provider_send()
    assert blocked.value.reason == "provider_send_blocked"


def test_peru_and_spain_share_one_intercepted_flow(tmp_path):
    pages = {}
    for profile in (PERU, SPAIN):
        root = tmp_path / profile.jurisdiction
        root.mkdir()
        lab = _laboratory(root, profile)
        try:
            _permit(lab, profile)
            federation, reads = _federation(profile)
            gemini, sends = _gemini(lambda request, payload=_summary(profile): httpx.Response(
                200, json=_body(payload), request=request))
            graph = JurisdictionLabGraph(
                _gateway(lab), federation, lambda _event: None, root / "review.sqlite3", profile)
            state = graph.invoke(
                lab.executor[profile.organization_id], profile.authorization_id, 1000,
                profile.patient_value, _consent(lab, profile, gemini))
            assert state["phase"] == "PENDING_REVIEW"
            assert state["response_status"] == "intercepted"
            assert state["requests_sent"] == 1
            assert graph.model_calls == 1
            assert reads[0].url.host == "127.0.0.1"
            assert sends[0].url.host == "generativelanguage.googleapis.com"
            case = read_review(root / "review.sqlite3", state["review_id"])
            assert case["status"] == "pending"
            assert {item["code"] for item in case["clinical_evidence"]} == {item.code for item in profile.observations}
            assert {item["value"] for item in case["clinical_evidence"]} == {item.value for item in profile.observations}
            assert case["clinical_evidence"][0]["validation_class"] == "internal-demo-rules"
            case["organization_id"] = profile.organization_id
            page = _detail(case, _Page())
            assert profile.profile_id in page
            assert "regla interna de demostración" in page
            assert "interceptado" in page
            assert "RENHICE" in page and "HCDSNS" in page
            pages[profile.jurisdiction] = page
            original = case["summary"]
            decided = _decide(root / "review.sqlite3", state["review_id"], profile, "reviewer-" + profile.jurisdiction.lower())
            assert decided["summary"] == original
            assert read_status(root / "review.sqlite3", state["review_id"]) == "pending"
        finally:
            lab.close()
    assert "718-7" in pages["PE"] and "2345-7" not in pages["PE"]
    assert "2345-7" in pages["ES"] and "718-7" not in pages["ES"]


def test_safety_cases_fail_closed(tmp_path):
    root = tmp_path / "safety"
    root.mkdir()
    lab = _laboratory(root, PERU)
    try:
        _permit(lab, PERU)
        _expect(lab, PERU, root / "fhir.sqlite3", _broken(_envelope(PERU)), "response_rejected")
        _expect(lab, PERU, root / "ucum.sqlite3", _mutate(_envelope(PERU), quantity={"system": "http://example.org", "unit": "mmol/L", "code": "mmol/L"}), "context_rejected")
        _expect(lab, PERU, root / "other.sqlite3", _mutate(_envelope(PERU), subject="https://lab.local/jurisdiction/pe/Patient/es-pat-001"), "context_rejected")
        _expect(lab, PERU, root / "org.sqlite3", _mutate(_envelope(PERU), organization="org-es-lab-demo"), "organization_mismatch")
        _expect(lab, PERU, root / "country.sqlite3", _mutate(_envelope(PERU), profile_id="es-lab-demo-v1"), "jurisdiction_mismatch")
        _expect(lab, PERU, root / "mix.sqlite3", _mutate(_envelope(PERU), organization="org-es-lab-demo", profile_id="pe-lab-demo-v1"), "organization_mismatch")
        _expect(lab, PERU, root / "incomplete.sqlite3", _mutate(_envelope(PERU), drop_quantity=True), "context_incomplete")
        official = _envelope(PERU)
        official["entries"][1]["resource"]["meta"]["profile"] = [
            "https://www.gob.pe/minsa/RENHICE/fhir/StructureDefinition/Observation"]
        _expect(lab, PERU, root / "official.sqlite3", official, "profile_not_verified")
        both = _envelope(PERU)
        both["sources"].append(dict(both["sources"][0], sourceKey="es-lab-demo", organizationId="org-es-lab-demo"))
        _expect(lab, PERU, root / "border.sqlite3", both, "cross_border_denied")
        invented = json.loads(_summary(PERU))
        invented["statements"][0]["sources"][0]["id"] = "obs-invented"
        _expect(lab, PERU, root / "invented.sqlite3", _envelope(PERU), "invalid_output", model_payload=json.dumps(invented))
        assert not (root / "invented.sqlite3").exists()
    finally:
        lab.close()


def test_missing_permit_wrong_policy_and_review_isolation(tmp_path):
    lab = _laboratory(tmp_path, PERU)
    try:
        missing = _run(lab, PERU, tmp_path / "missing.sqlite3")
        assert missing["reason"] == "not_granted"
        federation, _reads = _federation(PERU)
        blocked = JurisdictionLabGraph(
            _gateway(lab), federation, lambda _event: None, tmp_path / "consent.sqlite3", PERU)
        denied_consent = blocked.invoke(
            lab.executor[PERU.organization_id], PERU.authorization_id, 1000, PERU.patient_value, None)
        assert denied_consent["reason"] == "model_denied"
        _permit(lab, PERU)
        lab.admin[SPAIN.organization_id] = lab.issuer.issue(SPAIN.organization_id)
        lab.executor[SPAIN.organization_id] = lab.issuer.issue(SPAIN.organization_id, "executor")
        _permit(lab, SPAIN, policy_ref=PERU.policy_ref)
        denied = _run(lab, SPAIN, tmp_path / "policy.sqlite3")
        assert denied["reason"] == "operation_denied"
        peru = _run(lab, PERU, tmp_path / "pe.sqlite3")
        spain_root = tmp_path / "spain-lab"
        spain_root.mkdir()
        spain_lab = _laboratory(spain_root, SPAIN)
        try:
            _permit(spain_lab, SPAIN)
            spain = _run(spain_lab, SPAIN, spain_root / "review.sqlite3")
            assert peru["phase"] == "PENDING_REVIEW" and spain["phase"] == "PENDING_REVIEW"
            pe_case = read_review(tmp_path / "pe.sqlite3", peru["review_id"])
            es_case = read_review(spain_root / "review.sqlite3", spain["review_id"])
            assert "718-7" in {item["code"] for item in pe_case["clinical_evidence"]}
            assert "718-7" not in {item["code"] for item in es_case["clinical_evidence"]}
            assert reviews_for_organization(tmp_path / "pe.sqlite3", SPAIN.organization_id) == set()
            with pytest.raises(ReviewError) as foreign:
                _decide(tmp_path / "pe.sqlite3", peru["review_id"], SPAIN, "reviewer-es")
            assert foreign.value.reason == "organization_denied"
            with pytest.raises(ReviewError) as auditor:
                IamReviewer(
                    iam_principal_id(ISSUER, "auditor-pe"), ISSUER, "auditor-pe", PERU.organization_id,
                    "clinical-auditor", "session-auditor")
            assert auditor.value.reason == "role_denied"
            before = pe_case["summary"]
            assert read_review(tmp_path / "pe.sqlite3", peru["review_id"])["summary"] == before
        finally:
            spain_lab.close()
        _permit(lab, PERU, authorization_id="external-reuse", operation_id=EXTERNAL_OPERATION_ID,
                policy_ref=EXTERNAL_POLICY_REF)
        reused = _run(lab, PERU, tmp_path / "reused.sqlite3")
        assert reused["reason"] == "replay_denied"
    finally:
        lab.close()


def test_minimize_rejects_a_foreign_chart_before_the_model():
    foreign = _envelope(SPAIN)
    with pytest.raises(ProviderError) as error:
        minimize_envelope(foreign, PERU)
    assert error.value.reason == "jurisdiction_mismatch"


def _laboratory(tmp_path, profile):
    lab = _ready(tmp_path)
    lab.ledger.migrate_to_v6(lab.admin["ORG-A"])
    lab.ledger.migrate_to_v7(lab.admin["ORG-A"])
    lab.ledger.migrate_to_v8(lab.admin["ORG-A"])
    lab.admin[profile.organization_id] = lab.issuer.issue(profile.organization_id)
    lab.executor[profile.organization_id] = lab.issuer.issue(profile.organization_id, "executor")
    return lab


def _permit(lab, profile, **overrides):
    values = dict(
        authorization_id=profile.authorization_id, organization_id=profile.organization_id,
        deployment_id="gemini-sdk-a", provider_id="gemini", model_id="gemini-3.5-flash-lite",
        resource_id=profile.patient_value, budget_ceiling_microusd=1000,
        operation_id=OPERATION_ID, policy_ref=profile.policy_ref,
        principal_id=lab.executor[profile.organization_id].principal_id)
    values.update(overrides)
    if "organization_id" in overrides and overrides["organization_id"] not in lab.admin:
        lab.admin[overrides["organization_id"]] = lab.issuer.issue(overrides["organization_id"])
    return _register(lab, **values)


def _consent(lab, profile, http_client):
    return OperationalJurisdictionConsent.issue(
        {"GEMINI_API_KEY": KEY}, profile=profile, principal_id=lab.executor[profile.organization_id].principal_id,
        phrase=PHRASE, interactive=True, http_client=http_client)


def _federation(profile, payload=None):
    reads = []
    body = _envelope(profile) if payload is None else payload

    def handler(request):
        reads.append(request)
        return httpx.Response(200, json=body, request=request)

    federation = ClinicalFederationClient(
        "http://127.0.0.1:18281", "lab-token", organization_id=CALLER_ORGANIZATION,
        patient_system_key=CALLER_SYSTEM, patient_identifier_system=profile.patient_system,
        sources=(profile.source_key,), http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    return federation, reads


def _run(lab, profile, path, permit=None, operation_override=False):
    if permit is not None:
        _permit(lab, permit)
    federation, _reads = _federation(profile)
    gemini, _sends = _gemini(lambda request: httpx.Response(200, json=_body(_summary(profile)), request=request))
    graph = JurisdictionLabGraph(_gateway(lab), federation, lambda _event: None, path, profile)
    return graph.invoke(
        lab.executor[profile.organization_id], profile.authorization_id, 1000,
        profile.patient_value, _consent(lab, profile, gemini))


def _expect(lab, profile, path, payload, reason, model_payload=None):
    federation, _reads = _federation(profile, payload)
    text = model_payload if model_payload is not None else _summary(profile)
    gemini, _sends = _gemini(lambda request, body=text: httpx.Response(200, json=_body(body), request=request))
    graph = JurisdictionLabGraph(_gateway(lab), federation, lambda _event: None, path, profile)
    state = graph.invoke(
        lab.executor[profile.organization_id], profile.authorization_id, 1000,
        profile.patient_value, _consent(lab, profile, gemini))
    assert state["reason"] == reason
    assert state["phase"] == "FAILED"


def _decide(path, review_id, profile, subject):
    from app.clinical_lab_summary.review import decide
    reviewer = IamReviewer(
        iam_principal_id(ISSUER, subject), ISSUER, subject, profile.organization_id,
        "clinical-reviewer", "session-" + subject)
    return decide(path, review_id, reviewer, "approved", "sintetica", "2026-11-17T18:00:00.000000Z")


def _summary(profile):
    return json.dumps({
        "kind": OPERATION_ID,
        "review": "pending_human_review",
        "statements": [
            {
                "text": "Valor " + item.value + " " + item.unit,
                "sources": [{"source": profile.source_key, "resourceType": "Observation", "id": item.resource_id}],
            }
            for item in profile.observations
        ],
    })


def _envelope(profile):
    def tags(observation):
        found = [
            {"system": "https://lab.local/jurisdiction/profile", "code": profile.profile_id},
            {"system": "https://lab.local/jurisdiction/profile-version", "code": profile.version},
            {"system": "https://lab.local/jurisdiction/validation", "code": "internal-demo-rules"},
            {"system": "https://lab.local/jurisdiction/validation", "code": "fhir-r4-checked"},
        ]
        if observation:
            found.append({"system": "https://lab.local/jurisdiction/validation", "code": "quantity-verified"})
        return found

    patient = {
        "resourceType": "Patient",
        "id": profile.logical_id,
        "identifier": [{"system": profile.patient_system, "value": profile.patient_value}],
        "meta": {"source": profile.source_key, "tag": tags(False)},
    }
    entries = [{
        "sourceKey": profile.source_key,
        "organizationId": profile.organization_id,
        "fullUrl": profile.base_url + "/Patient/" + profile.logical_id,
        "resource": patient,
    }]
    for item in profile.observations:
        value = float(item.value) if "." in item.value else int(item.value)
        entries.append({
            "sourceKey": profile.source_key,
            "organizationId": profile.organization_id,
            "fullUrl": profile.base_url + "/Observation/" + item.resource_id,
            "resource": {
                "resourceType": "Observation",
                "id": item.resource_id,
                "status": "final",
                "subject": {"reference": profile.base_url + "/Patient/" + profile.logical_id},
                "code": {"coding": [{"system": "http://loinc.org", "code": item.code}]},
                "valueQuantity": {"value": value, "unit": item.unit, "system": "http://unitsofmeasure.org", "code": item.unit},
                "meta": {"source": profile.source_key, "tag": tags(True)},
            },
        })
    return {
        "contractVersion": "clinical-federation-v1",
        "status": "complete",
        "truncated": False,
        "sources": [{
            "sourceKey": profile.source_key,
            "organizationId": profile.organization_id,
            "outcome": "complete",
            "resourceCount": len(entries),
        }],
        "entries": entries,
    }


def _mutate(payload, **changes):
    body = copy.deepcopy(payload)
    resource = body["entries"][1]["resource"]
    if "quantity" in changes:
        resource["valueQuantity"].update(changes["quantity"])
    if "subject" in changes:
        resource["subject"]["reference"] = changes["subject"]
    if changes.get("drop_quantity"):
        resource.pop("valueQuantity")
    if "organization" in changes:
        body["sources"][0]["organizationId"] = changes["organization"]
        for entry in body["entries"]:
            entry["organizationId"] = changes["organization"]
    if "profile_id" in changes:
        for entry in body["entries"]:
            for tag in entry["resource"]["meta"]["tag"]:
                if tag["system"].endswith("/profile"):
                    tag["code"] = changes["profile_id"]
    return body


def _broken(payload):
    body = copy.deepcopy(payload)
    body["entries"][1]["resource"] = {"id": "broken"}
    return body


class _Page:
    mode = "development"
    permissions = frozenset()
    csrf = ""
