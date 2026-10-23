"""Explorer for stored demonstration reports. It does not start Docker."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.demo_experience import active_execution_id, read_report, timeline
from app.main import app, get_settings


EXECUTION = "E2E-20261023T141128Z-7C6DC4"
SECRET = "review-login-secret-value"


def _report() -> dict:
    return {
        "executionId": EXECUTION,
        "synthetic": True,
        "requestingOrganizationId": "org-mini-his",
        "protocolId": "CROSS_ORG_LAB_RESULT_REVIEW_V1",
        "review-login.secret": SECRET,
        "scenarios": [
            {
                "scenario": "negative",
                "patientId": "MHS-PAT-003",
                "hisEncounterId": "MHS-CON-003",
                "hisOrderId": "MHS-LAB-NEG",
                "lisOrderId": "MLS-ORD-NEG",
                "correlationId": "EXC-NEG",
                "resultState": "final_on_other_order",
                "federationStatus": "complete",
                "evaluationStatus": "not_matched",
                "currentStep": "completed",
                "langGraphStatus": "completed",
                "reviewCaseId": None,
                "evidence": [],
                "provenance": [],
            },
            {
                "scenario": "positive",
                "patientId": "<script>alert(1)</script>",
                "hisEncounterId": "MHS-CON-002",
                "hisOrderId": "MHS-LAB-POS",
                "lisOrderId": "MLS-ORD-POS",
                "correlationId": "EXC-POS",
                "resultState": "final",
                "federationStatus": "complete",
                "protocolId": "CROSS_ORG_LAB_RESULT_REVIEW_V1",
                "evaluationStatus": "matched",
                "currentStep": "await_human",
                "langGraphStatus": "waiting_human",
                "reviewCaseId": "136abd43-f26c-4041-883c-894a55847834",
                "evidence": [
                    "Encounter/MHS-CON-002",
                    "ServiceRequest/MHS-LAB-POS",
                    "ServiceRequest/MLS-ORD-POS",
                    "Observation/MLS-RES-POS",
                ],
                "evidenceProjection": [
                    {
                        "reference": "Observation/MLS-RES-POS",
                        "resourceType": "Observation",
                        "sourceKey": "mini-lis",
                        "source": "https://lab.local/mini-lis",
                        "status": "final",
                    }
                ],
                "provenance": [
                    {
                        "reference": "Encounter/MHS-CON-002",
                        "sourceKey": "mini-his",
                        "source": "https://lab.local/mini-his",
                    }
                ],
            },
        ],
    }


def test_positive_and_negative_timelines_follow_the_report():
    report = _report()
    negative = timeline(report["scenarios"][0])
    positive = timeline(report["scenarios"][1])
    assert negative[-1]["status"] == "sin caso"
    assert "No se generó" in negative[-1]["detail"]
    assert any(item["title"] == "Resultado de laboratorio" and item["status"] == "otra orden" for item in negative)
    assert positive[-1]["status"] == "caso abierto"
    assert any(item["status"] == "registrada" and "matched" in item["detail"] for item in positive)
    assert any(item["detail"] == "Encounter/MHS-CON-002" for item in positive)


def test_missing_fields_are_not_marked_complete():
    stages = timeline({"scenario": "positive"})
    assert all(item["status"] == "sin evidencia" for item in stages)


def test_historical_report_without_projection_keeps_references(tmp_path, monkeypatch):
    monkeypatch.setenv("DEMO_EXPERIENCE_REPORT_ROOT", str(tmp_path))
    execution = tmp_path / EXECUTION
    execution.mkdir()
    historical = _report()
    historical["scenarios"][1].pop("evidenceProjection")
    (execution / "report.json").write_text(json.dumps(historical), encoding="utf-8")
    (execution / "review-login.secret").write_text(SECRET, encoding="utf-8")
    loaded = read_report(tmp_path, EXECUTION)
    assert loaded is not None
    assert SECRET not in json.dumps(loaded)
    from app.demo_experience import _execution_body

    html = _execution_body(loaded, active=False)
    assert "reporte histórico" in html
    assert "Este reporte histórico no guardó la proyección JSON" in html
    assert "Encounter/MHS-CON-002" in html
    assert "origen mini-his" in html
    assert SECRET not in html
    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html
    assert 'href="/review-cases/136abd43-f26c-4041-883c-894a55847834"' not in html
    assert "no tiene ese caso y no lo restaura" in html
    assert "No se generó revisión humana." in html


def test_review_link_appears_only_when_this_instance_has_the_case():
    from app.demo_experience import _execution_body

    html = _execution_body(
        _report(),
        active=True,
        local_cases={"136abd43-f26c-4041-883c-894a55847834": "open"},
    )
    assert 'href="/review-cases/136abd43-f26c-4041-883c-894a55847834"' in html
    assert "Estado en esta instancia: abierto." in html
    assert "no lo restaura" not in html


def test_active_execution_is_distinct_and_traversal_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("DEMO_EXPERIENCE_REPORT_ROOT", str(tmp_path))
    (tmp_path / "current.json").write_text(
        json.dumps({"executionId": EXECUTION, "running": True, "container": "e2e-demo-pg"}),
        encoding="utf-8",
    )
    assert active_execution_id(tmp_path) == EXECUTION
    assert read_report(tmp_path, "../review-login.secret") is None
    assert read_report(tmp_path, "E2E-20261023T000000Z-AAAAAA/../../windows") is None
    assert read_report(tmp_path, EXECUTION) is None


def test_route_does_not_publish_a_report_without_a_session(monkeypatch):
    monkeypatch.setenv("HUMAN_REVIEW_DEVELOPMENT_AUTH_ENABLED", "false")
    get_settings.cache_clear()
    try:
        response = TestClient(app).get("/demo-experience/" + EXECUTION, follow_redirects=False)
        assert response.status_code in {303, 503}
        assert SECRET not in response.text
        assert "MHS-PAT-003" not in response.text
    finally:
        get_settings.cache_clear()


def test_invalid_execution_id_is_not_a_file_path(tmp_path):
    assert read_report(tmp_path, "..\\review-login.secret") is None
    assert read_report(tmp_path, "E2E-20261023T141128Z-7C6DC4/report.json") is None
