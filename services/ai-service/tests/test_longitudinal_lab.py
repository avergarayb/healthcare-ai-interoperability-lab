"""Dated comparison for Peru and Spain. The model describes a difference it does not calculate."""
import copy
import json
import socket

import httpx
import pytest

from app.clinical_federation_client import ClinicalFederationClient
from app.clinical_lab_summary.http import _detail
from app.clinical_lab_summary.review import (
    IamReviewer, ReviewError, iam_principal_id, read_review, reviews_for_organization,
)
from app.enterprise_ai_processing.execution_types import ExecutionError
from app.enterprise_ai_processing.remote_authorization import (
    JURISDICTION_OPERATION_ID, JURISDICTION_POLICY_REFS,
)
from app.enterprise_llm_providers.errors import ProviderError
from app.jurisdiction_lab.context import minimize_envelope
from app.jurisdiction_lab.mcp_tool import handle as jurisdiction_handle
from app.jurisdiction_lab.profile import CALLER_ORGANIZATION, CALLER_SYSTEM, PERU, SPAIN
from app.longitudinal_lab.compare import compare_envelope
from app.longitudinal_lab.consent import PHRASE, OperationalLongitudinalConsent
from app.longitudinal_lab.context import validate_summary
from app.longitudinal_lab.graph import LongitudinalLabGraph
from app.longitudinal_lab.mcp_tool import TOOL_NAME, handle
from app.longitudinal_lab.policy import request_real_provider_send
from app.longitudinal_lab.series import OPERATION_ID, PERU as PERU_SERIES, SPAIN as SPAIN_SERIES, series_for
from tests.test_lab_summary import _gemini
from tests.test_model_gateway_durable_authorization import _gateway, _ready, _register
from tests.test_model_gateway_egress_gemini import KEY, _body


ISSUER = "http://127.0.0.1:18294/realms/lab-review-iam"
TAG = "https://lab.local/jurisdiction/validation"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("provider socket forbidden")

    monkeypatch.setattr(socket, "socket", forbidden)


def test_deterministic_pairs_and_closed_denials():
    peru_chart, peru_evidence = compare_envelope(_envelope(PERU), PERU)
    spain_chart, spain_evidence = compare_envelope(_envelope(SPAIN), SPAIN)
    assert peru_chart["absolute_difference"] == "+0.6"
    assert peru_chart["direction"] == "aumento"
    assert peru_chart["percent_difference"] == "+4.6875"
    assert peru_chart["prior_date"] < peru_chart["recent_date"]
    assert peru_evidence["patient_id"] == "PE-PAT-001"
    assert peru_evidence["prior_value"] == "12.8" and peru_evidence["recent_value"] == "13.4"
    assert spain_chart["absolute_difference"] == "-5"
    assert spain_chart["direction"] == "disminucion"
    assert spain_chart["percent_difference"] == "-5.2632"
    assert spain_evidence["code"] == "2345-7"
    assert "PE-PAT-001" not in json.dumps(spain_chart)

    zero = _envelope(PERU)
    for entry in _tagged(zero):
        entry["resource"]["valueQuantity"]["value"] = 13.4
    zero_chart, _zero_evidence = compare_envelope(zero, PERU)
    assert zero_chart["absolute_difference"] == "0"
    assert zero_chart["direction"] == "sin cambio"
    assert zero_chart["percent_difference"] == "0"

    baseline = _envelope(PERU)
    _tagged(baseline)[0]["resource"]["valueQuantity"]["value"] = 0
    with pytest.raises(ProviderError) as zero_base:
        compare_envelope(baseline, PERU)
    assert zero_base.value.reason == "zero_baseline"

    cases = {
        "patient_mismatch": lambda body: _subject(body, PERU.base_url + "/Patient/other"),
        "organization_mismatch": lambda body: _organization(body, "org-es-lab-demo"),
        "jurisdiction_mismatch": lambda body: _source(body, "es-lab-demo"),
        "code_mismatch": lambda body: _coding(body, "code", "6690-2"),
        "code_system_mismatch": lambda body: _coding(body, "system", "http://snomed.info/sct"),
        "ucum_unknown": lambda body: _quantity(body, "system", "http://example.org/unit"),
        "unit_mismatch": lambda body: (_quantity(body, "unit", "mmol/L"), _quantity(body, "code", "mmol/L")),
        "context_rejected": lambda body: _tagged(body)[1]["resource"]["specimen"].update({"reference": "Specimen/other"}),
        "context_insufficient": lambda body: _tagged(body)[0]["resource"].pop("specimen"),
        "date_absent": lambda body: _drop_date(body),
        "date_unsupported": lambda body: _period(body, keep_date=False),
        "date_ambiguous": lambda body: _period(body, keep_date=True),
        "status_rejected": lambda body: _tagged(body)[0]["resource"].update({"status": "preliminary"}),
        "value_rejected": lambda body: _quantity(body, "value", "12.8"),
        "comparator_unsupported": lambda body: _quantity(body, "comparator", ">"),
        "ambiguous_duplicate": lambda body: body["entries"].append(copy.deepcopy(_tagged(body)[1])),
        "context_incomplete": lambda body: body.update({"status": "partial"}),
        "cross_border_denied": lambda body: body["sources"].append(
            {"sourceKey": "es-lab-demo", "organizationId": SPAIN.organization_id, "outcome": "complete"}),
    }
    for reason, mutate in cases.items():
        payload = _envelope(PERU)
        mutate(payload)
        with pytest.raises(ProviderError) as error:
            compare_envelope(payload, PERU)
        assert error.value.reason == reason

    method = _envelope(PERU)
    _tagged(method)[1]["resource"]["method"]["coding"][0]["code"] = "capillary-v1"
    with pytest.raises(ProviderError) as method_error:
        compare_envelope(method, PERU)
    assert method_error.value.reason == "context_rejected"

    cancelled = _envelope(PERU)
    _tagged(cancelled)[0]["resource"]["status"] = "cancelled"
    with pytest.raises(ProviderError) as cancelled_error:
        compare_envelope(cancelled, PERU)
    assert cancelled_error.value.reason == "status_rejected"

    same_time = _envelope(PERU)
    _tagged(same_time)[1]["resource"]["effectiveDateTime"] = _tagged(same_time)[0]["resource"]["effectiveDateTime"]
    with pytest.raises(ProviderError) as duplicate_time:
        compare_envelope(same_time, PERU)
    assert duplicate_time.value.reason == "ambiguous_duplicate"

    summary = minimize_envelope(_envelope(PERU), PERU)
    assert {item["id"] for item in summary["facts"]} == {"pe-obs-718-7", "pe-obs-6690-2"}
    listed = jurisdiction_handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, {}, None, None)
    assert [item["name"] for item in listed["result"]["tools"]] == ["read_jurisdiction_lab_chart"]
    denied = handle(
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
         "params": {"name": TOOL_NAME, "arguments": {"patient_id": "PE-PAT-001", "organization": "org-es-lab-demo"}}},
        {"profile": PERU, "patient_id": "PE-PAT-001", "operation_id": OPERATION_ID,
         "authorization_id": PERU_SERIES.authorization_id},
        None, None)
    assert denied["error"]["message"] == "scope_mismatch"


def test_peru_and_spain_end_pending_review(tmp_path):
    lab = _laboratory(tmp_path, PERU)
    try:
        peru = _run(lab, PERU, tmp_path / "peru" / "review.sqlite3")
        spain_root = tmp_path / "spain-lab"
        spain_root.mkdir()
        spain_lab = _laboratory(spain_root, SPAIN)
        try:
            spain = _run(spain_lab, SPAIN, spain_root / "review.sqlite3")
            assert peru["phase"] == "PENDING_REVIEW" and spain["phase"] == "PENDING_REVIEW"
            assert peru["response_status"] == "intercepted" and spain["response_status"] == "intercepted"
            pe_case = read_review(tmp_path / "peru" / "review.sqlite3", peru["review_id"])
            es_case = read_review(spain_root / "review.sqlite3", spain["review_id"])
            assert pe_case["longitudinal_evidence"][0]["absolute_difference"] == "+0.6"
            assert es_case["longitudinal_evidence"][0]["absolute_difference"] == "-5"
            assert pe_case["longitudinal_evidence"][0]["code"] == "718-7"
            assert "718-7" not in {item["code"] for item in es_case["longitudinal_evidence"]}
            assert pe_case["summary"]["statements"][0]["text"] != pe_case["longitudinal_evidence"][0]["prior_value"]
            page = _detail(pe_case, _page())
            assert "Comparación longitudinal" in page
            assert "12.8" in page and "13.4" in page and "+0.6" in page
            assert "2026-10-01" in page and "2026-11-15" in page
            assert "interceptado" in page
            assert reviews_for_organization(tmp_path / "peru" / "review.sqlite3", SPAIN.organization_id) == set()
            before = pe_case["summary"]
            evidence_before = pe_case["longitudinal_evidence"]
            decision = _decide(tmp_path / "peru" / "review.sqlite3", peru["review_id"], PERU, "reviewer-pe")
            assert decision["decision"]["decision"] == "approved"
            after = read_review(tmp_path / "peru" / "review.sqlite3", peru["review_id"])
            assert after["summary"] == before
            assert after["status"] == "pending"
            assert after["longitudinal_evidence"] == evidence_before
            with pytest.raises(ReviewError) as second:
                _decide(tmp_path / "peru" / "review.sqlite3", peru["review_id"], PERU, "reviewer-pe")
            assert second.value.reason == "already_decided"
            with pytest.raises(ReviewError) as foreign:
                _decide(tmp_path / "peru" / "review.sqlite3", peru["review_id"], SPAIN, "reviewer-es")
            assert foreign.value.reason == "organization_denied"
            with pytest.raises(ReviewError) as auditor:
                IamReviewer(
                    iam_principal_id(ISSUER, "auditor-pe"), ISSUER, "auditor-pe", PERU.organization_id,
                    "clinical-auditor", "session-auditor")
            assert auditor.value.reason == "role_denied"
        finally:
            spain_lab.close()
    finally:
        lab.close()


def test_authorization_and_model_stay_closed(tmp_path):
    missing_lab = _laboratory(tmp_path / "missing", PERU)
    try:
        missing = _run(missing_lab, PERU, tmp_path / "missing" / "review.sqlite3", permit=False)
        assert missing["reason"] == "not_granted"
    finally:
        missing_lab.close()
    other_lab = _laboratory(tmp_path / "other", PERU)
    try:
        _permit(other_lab, PERU, operation_id=JURISDICTION_OPERATION_ID,
                policy_ref=next(iter(JURISDICTION_POLICY_REFS)))
        reused_operation = _run(other_lab, PERU, tmp_path / "other" / "review.sqlite3", permit=False)
        assert reused_operation["reason"] == "operation_denied"
    finally:
        other_lab.close()
    policy_lab = _laboratory(tmp_path / "policy", PERU)
    try:
        _permit(policy_lab, PERU, policy_ref=SPAIN_SERIES.policy_ref)
        wrong_policy = _run(policy_lab, PERU, tmp_path / "policy" / "review.sqlite3", permit=False)
        assert wrong_policy["reason"] == "operation_denied"
    finally:
        policy_lab.close()
    once_lab = _laboratory(tmp_path / "once", PERU)
    try:
        _permit(once_lab, PERU)
        first = _run(once_lab, PERU, tmp_path / "once" / "review.sqlite3", permit=False)
        assert first["phase"] == "PENDING_REVIEW"
        again = _run(once_lab, PERU, tmp_path / "again" / "review.sqlite3", permit=False)
        assert again["reason"] == "replay_denied"
    finally:
        once_lab.close()
    changed_lab = _laboratory(tmp_path / "changed", PERU)
    try:
        _permit(changed_lab, PERU)
        chart, _evidence = compare_envelope(_envelope(PERU), PERU)
        changed_text = _summary(chart, PERU).replace("+0.6", "+9.9")
        changed_run = _run(
            changed_lab, PERU, tmp_path / "changed" / "review.sqlite3", permit=False, model_text=changed_text)
        assert changed_run["reason"] == "invalid_output"
        assert changed_run["phase"] == "FAILED"
    finally:
        changed_lab.close()
    chart, _evidence = compare_envelope(_envelope(PERU), PERU)
    parsed = json.loads(_summary(chart, PERU))
    parsed["statements"][0]["text"] = parsed["statements"][0]["text"].replace("+0.6", "+9.9")
    with pytest.raises(ProviderError) as changed:
        validate_summary(chart, parsed, PERU)
    assert changed.value.reason == "invalid_output"
    invented = json.loads(_summary(chart, PERU))
    invented["statements"][0]["sources"][0]["id"] = "invented-obs"
    with pytest.raises(ProviderError) as invented_error:
        validate_summary(chart, invented, PERU)
    assert invented_error.value.reason == "invalid_output"
    diagnosed = json.loads(_summary(chart, PERU))
    diagnosed["statements"][0]["text"] += " diagnostico"
    with pytest.raises(ProviderError) as diagnosis:
        validate_summary(chart, diagnosed, PERU)
    assert diagnosis.value.reason == "invalid_output"
    with pytest.raises(ProviderError) as blocked:
        request_real_provider_send()
    assert blocked.value.reason == "provider_send_blocked"
    with pytest.raises(ProviderError) as no_client:
        OperationalLongitudinalConsent.issue(
            {"GEMINI_API_KEY": KEY}, profile=PERU, principal_id="synthetic-executor",
            phrase=PHRASE, interactive=True, http_client=None)
    assert no_client.value.reason == "provider_send_blocked"
    stopped = _laboratory_v8(tmp_path / "v8")
    try:
        with pytest.raises(ExecutionError) as old_schema:
            _permit(stopped, PERU)
        assert old_schema.value.reason == "authority_unverifiable"
    finally:
        stopped.close()


def _laboratory(tmp_path, profile):
    tmp_path.mkdir(parents=True, exist_ok=True)
    lab = _ready(tmp_path)
    lab.ledger.migrate_to_v6(lab.admin["ORG-A"])
    lab.ledger.migrate_to_v7(lab.admin["ORG-A"])
    lab.ledger.migrate_to_v8(lab.admin["ORG-A"])
    lab.ledger.migrate_to_v9(lab.admin["ORG-A"])
    lab.admin[profile.organization_id] = lab.issuer.issue(profile.organization_id)
    lab.executor[profile.organization_id] = lab.issuer.issue(profile.organization_id, "executor")
    return lab


def _laboratory_v8(tmp_path):
    tmp_path.mkdir()
    lab = _ready(tmp_path)
    lab.ledger.migrate_to_v6(lab.admin["ORG-A"])
    lab.ledger.migrate_to_v7(lab.admin["ORG-A"])
    lab.ledger.migrate_to_v8(lab.admin["ORG-A"])
    lab.admin[PERU.organization_id] = lab.issuer.issue(PERU.organization_id)
    lab.executor[PERU.organization_id] = lab.issuer.issue(PERU.organization_id, "executor")
    return lab


def _permit(lab, profile, **overrides):
    series = series_for(profile)
    values = dict(
        authorization_id=series.authorization_id, organization_id=profile.organization_id,
        deployment_id="gemini-sdk-a", provider_id="gemini", model_id="gemini-3.5-flash-lite",
        resource_id=profile.patient_value, budget_ceiling_microusd=1000,
        operation_id=OPERATION_ID, policy_ref=series.policy_ref,
        principal_id=lab.executor[profile.organization_id].principal_id)
    values.update(overrides)
    if values["organization_id"] not in lab.admin:
        lab.admin[values["organization_id"]] = lab.issuer.issue(values["organization_id"])
    return _register(lab, **values)


def _run(lab, profile, path, permit=True, model_text=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    if permit:
        _permit(lab, profile)
    federation, _reads = _federation(profile)
    chart, _evidence = compare_envelope(_envelope(profile), profile)
    payload = model_text if model_text is not None else _summary(chart, profile)
    gemini, sends = _gemini(lambda request: httpx.Response(200, json=_body(payload), request=request))
    graph = LongitudinalLabGraph(_gateway(lab), federation, lambda _event: None, path, profile)
    state = graph.invoke(
        lab.executor[profile.organization_id], series_for(profile).authorization_id, 1000,
        profile.patient_value, _consent(lab, profile, gemini))
    assert all(request.url.host != "api.openai.com" for request in sends)
    return state


def _consent(lab, profile, http_client):
    return OperationalLongitudinalConsent.issue(
        {"GEMINI_API_KEY": KEY}, profile=profile, principal_id=lab.executor[profile.organization_id].principal_id,
        phrase=PHRASE, interactive=True, http_client=http_client)


def _federation(profile):
    def handler(request):
        return httpx.Response(200, json=_envelope(profile), request=request)

    return ClinicalFederationClient(
        "http://127.0.0.1:18281", "lab-token", organization_id=CALLER_ORGANIZATION,
        patient_system_key=CALLER_SYSTEM, patient_identifier_system=profile.patient_system,
        sources=(profile.source_key,), http_client=httpx.Client(transport=httpx.MockTransport(handler))), None


def _summary(chart, profile):
    difference = "diferencia 0" if chart["absolute_difference"] == "0" else "Diferencia " + chart["absolute_difference"]
    percent = "porcentaje 0" if chart["percent_difference"] == "0" else "Porcentaje " + chart["percent_difference"]
    text = (
        "Codigo " + chart["code"] + " paso de " + chart["prior_value"] + " " + chart["unit"]
        + " el " + chart["prior_date"][:10] + " a " + chart["recent_value"] + " " + chart["unit"]
        + " el " + chart["recent_date"][:10] + ". " + difference + ". " + percent + ". "
        + chart["prior_reference"] + " " + chart["recent_reference"]
    )
    return json.dumps({
        "kind": OPERATION_ID,
        "review": "pending_human_review",
        "statements": [{
            "text": text,
            "sources": [
                {"source": profile.source_key, "resourceType": "Observation", "id": chart["prior_reference"]},
                {"source": profile.source_key, "resourceType": "Observation", "id": chart["recent_reference"]},
            ],
        }],
    })


def _decide(path, review_id, profile, subject):
    from app.clinical_lab_summary.review import decide
    reviewer = IamReviewer(
        iam_principal_id(ISSUER, subject), ISSUER, subject, profile.organization_id,
        "clinical-reviewer", "session-" + subject)
    return decide(path, review_id, reviewer, "approved", "sintetica", "2026-11-17T18:00:00.000000Z")


def _envelope(profile):
    series = series_for(profile)

    def tags(observation, longitudinal=False):
        found = [
            {"system": "https://lab.local/jurisdiction/profile", "code": profile.profile_id},
            {"system": "https://lab.local/jurisdiction/profile-version", "code": profile.version},
            {"system": "https://lab.local/jurisdiction/validation", "code": "internal-demo-rules"},
            {"system": "https://lab.local/jurisdiction/validation", "code": "fhir-r4-checked"},
        ]
        if observation:
            found.append({"system": TAG, "code": "quantity-verified"})
        if longitudinal:
            found.append({"system": TAG, "code": "longitudinal-series"})
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
        entries.append(_observation(profile, item.resource_id, item.code, value, item.unit, None, None, tags(True)))
    for point in (series.prior, series.recent):
        value = float(point.value) if "." in point.value else int(point.value)
        entries.append(_observation(
            profile, point.resource_id, series.code, value, series.unit, point.effective, series, tags(True, True)))
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


def _observation(profile, resource_id, code, value, unit, effective, series, tags):
    resource = {
        "resourceType": "Observation",
        "id": resource_id,
        "status": "final",
        "subject": {"reference": profile.base_url + "/Patient/" + profile.logical_id},
        "code": {"coding": [{"system": "http://loinc.org", "code": code}]},
        "valueQuantity": {"value": value, "unit": unit, "system": "http://unitsofmeasure.org", "code": unit},
        "meta": {"source": profile.source_key, "tag": tags},
    }
    if effective is not None:
        resource["effectiveDateTime"] = effective
        resource["specimen"] = {"reference": series.specimen}
        resource["method"] = {"coding": [{"system": series.method_system, "code": series.method_code}]}
    return {
        "sourceKey": profile.source_key,
        "organizationId": profile.organization_id,
        "fullUrl": profile.base_url + "/Observation/" + resource_id,
        "resource": resource,
    }


def _tagged(body):
    return [
        entry for entry in body["entries"]
        if any(tag.get("code") == "longitudinal-series" for tag in entry["resource"].get("meta", {}).get("tag", []))
    ]


def _subject(body, reference):
    _tagged(body)[1]["resource"]["subject"]["reference"] = reference


def _organization(body, organization):
    body["sources"][0]["organizationId"] = organization
    for entry in body["entries"]:
        entry["organizationId"] = organization


def _source(body, source):
    body["sources"][0]["sourceKey"] = source
    for entry in body["entries"]:
        entry["sourceKey"] = source
        entry["resource"]["meta"]["source"] = source


def _coding(body, key, value):
    _tagged(body)[1]["resource"]["code"]["coding"][0][key] = value


def _quantity(body, key, value):
    _tagged(body)[1]["resource"]["valueQuantity"][key] = value


def _drop_date(body):
    resource = _tagged(body)[0]["resource"]
    resource.pop("effectiveDateTime")
    resource["issued"] = "2026-10-01T08:00:00Z"


def _period(body, keep_date):
    resource = _tagged(body)[0]["resource"]
    resource["effectivePeriod"] = {"start": "2026-10-01T08:00:00Z"}
    if not keep_date:
        resource.pop("effectiveDateTime")


def _page():
    class _Page:
        mode = "development"
        permissions = frozenset({"decide"})
        csrf = ""
    return _Page()
