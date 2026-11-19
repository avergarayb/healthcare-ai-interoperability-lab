"""Showcase adapter: one real graph, one permit, and a human decision."""
import json

import httpx
from starlette.requests import Request

from app.clinical_federation_client import ClinicalFederationClient
from app.clinical_lab_summary.showcase_http import decide_summary, prepare_summary, replay_summary
from app.clinical_lab_summary.showcase_run import decide_case, prepare_case, read_case, replay_case
from app.config import Settings


PATIENT = "MHS-PAT-001"


def _settings():
    return Settings(
        model_boundary_base_url="http://127.0.0.1:9",
        model_boundary_path="/api/model-boundary/v1",
        model_boundary_timeout_seconds=2,
        model_boundary_service_token="showcase-service-token",
        host="127.0.0.1",
        port=8090,
        llm_experimental_enabled=False,
        gemini_api_key="",
        gemini_model="gemini-flash-latest",
        followup_agent_enabled=False,
        ai_review_db_path="review.sqlite3",
        human_review_form_signing_secret="",
        institutional_knowledge_db_path="knowledge.sqlite3",
        institutional_knowledge_embedding_model="hash-v1",
        institutional_knowledge_min_score=0.68,
        human_session_db_path="session.sqlite3",
        human_review_development_auth_enabled=False,
        human_review_development_auth_secret="",
        human_review_development_principal_id="",
        human_review_development_principal_display_name="",
        clinical_context_mode="single",
        federation_participant_token="showcase-federation-token",
        federation_requesting_organization_id="",
        federation_patient_system_key="",
        federation_patient_identifier_system="",
        federation_sources=("mini-his", "mini-lis"),
        federation_timeout_seconds=2,
    )


def _request(token="showcase-service-token"):
    headers = []
    if token is not None:
        headers.append((b"x-service-token", token.encode("utf-8")))
    return Request({"type": "http", "headers": headers, "method": "POST", "path": "/"})


def _observation(source, observation_id, value):
    return {
        "sourceKey": source,
        "resource": {
            "resourceType": "Observation",
            "id": observation_id,
            "status": "final",
            "code": {"coding": [{"system": "http://loinc.org", "code": "718-7"}]},
            "valueQuantity": {
                "value": value,
                "unit": "g/dL",
                "system": "http://unitsofmeasure.org",
                "code": "g/dL",
            },
        },
    }


def _envelope():
    return {
        "contractVersion": "clinical-federation-v1",
        "status": "complete",
        "truncated": False,
        "correlationId": "FED-SHOWCASE000001",
        "sources": [
            {"sourceKey": "mini-his", "outcome": "complete"},
            {"sourceKey": "mini-lis", "outcome": "complete"},
        ],
        "entries": [
            {"sourceKey": "mini-his", "resource": {"resourceType": "Patient", "id": PATIENT}},
            _observation("mini-his", "MHS-RES-OLD", 13.4),
            _observation("mini-his", "MHS-RES-NOW", 12.8),
            _observation("mini-lis", "MLS-RES-NOW", 12.8),
        ],
    }


def _federation():
    def handler(request):
        return httpx.Response(200, json=_envelope(), request=request)

    return ClinicalFederationClient(
        "http://127.0.0.1:8081", "synthetic-token", organization_id="org-mini-his",
        patient_system_key="mini-his",
        patient_identifier_system="https://lab.local/mini-his/patient",
        sources=("mini-his", "mini-lis"),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_two_cases_keep_independent_permits_and_a_consumed_one_is_rejected(tmp_path):
    federation = _federation()
    first = prepare_case(tmp_path, federation, "clinica")
    assert first["phase"] == "PENDING_REVIEW"
    assert first["modelMode"] == "intercepted"
    assert first["tool"] == "read_federated_lab_chart"
    assert first["patientId"] == PATIENT
    assert first["organizationId"] == "org-mini-his"
    assert first["correlationId"] == "FED-SHOWCASE000001"
    assert [item["id"] for item in first["current"]] == ["MHS-RES-NOW", "MLS-RES-NOW"]
    assert [item["id"] for item in first["historical"]] == ["MHS-RES-OLD"]
    assert "13.4" in first["statements"][2]["text"] or any("13.4" in item["text"] for item in first["statements"])
    assert "showcase-intercepted" not in json.dumps(first)
    decided = decide_case(tmp_path, first["caseId"], "approved")
    assert decided["decision"]["decision"] == "approved"
    assert decided["decision"]["reviewer"] == "hl7-reviewer"
    assert decided["decision"]["authenticator"] == "DEVELOPMENT_AUTHENTICATOR_V1"
    try:
        decide_case(tmp_path, first["caseId"], "rejected")
    except Exception as error:
        assert error.reason == "already_decided"
    else:
        raise AssertionError("second decision")
    try:
        replay_case(tmp_path, first["caseId"], federation)
    except Exception as error:
        assert error.reason == "replay_denied"
    else:
        raise AssertionError("consumed permit")
    second = prepare_case(tmp_path, federation, "clinica")
    assert second["caseId"] != first["caseId"]
    assert second["reviewStatus"] == "pending"
    stored = read_case(tmp_path, first["caseId"])
    assert stored["decision"]["decision"] == "approved"


def test_http_denies_the_wrong_role_organization_and_token():
    settings = _settings()
    body = json.dumps({
        "role": "auditor", "organizationId": "org-mini-his", "actorId": "auditor",
    }).encode("utf-8")
    denied = prepare_summary(_request(), settings, body)
    assert denied.status_code == 403
    assert denied.body
    assert b"role_denied" in denied.body
    other = json.dumps({
        "role": "clinician", "organizationId": "org-other", "actorId": "clinica",
    }).encode("utf-8")
    isolated = decide_summary(_request(), settings, "sum-0123456789ab", other)
    assert isolated.status_code == 403
    assert b"organization_denied" in isolated.body
    missing = replay_summary(_request(None), settings, "sum-0123456789ab", other)
    assert missing.status_code == 401
