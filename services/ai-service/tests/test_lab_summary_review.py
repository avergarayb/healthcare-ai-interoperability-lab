"""Human decisions for one lab summary. No model and no follow-up case store."""
import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.clinical_lab_summary.review import (
    ReviewError, Reviewer, decide, list_reviews, prepare_decision_store, queue_summary, read_review,
)
from app.config import Settings
from app.human_development_auth import SESSION_COOKIE
from app.human_session import DEVELOPMENT_AUTHENTICATOR_V1
from app.main import app, get_settings


SUMMARY = {
    "kind": "lab-result-summary-v1",
    "review": "pending_human_review",
    "statements": [{
        "text": "Hemoglobina 13.4 g/dL",
        "sources": [{"source": "mini-his", "resourceType": "Observation", "id": "MHS-RES-001"}],
    }],
}
REVIEW_ID = "c934921a-8089-4592-9813-c71821496534"
WHEN = "2026-11-17T17:10:00.000000Z"
ORIGIN = {"origin": "http://127.0.0.1"}


def _seed(path):
    queue_summary(path, REVIEW_ID, "e2e-clinical-001-gemini", "MHS-PAT-001", SUMMARY)


def _reviewer(principal="lab-reviewer"):
    return Reviewer(principal, DEVELOPMENT_AUTHENTICATOR_V1, "session-1")


def _original(path):
    with sqlite3.connect(path) as connection:
        return connection.execute(
            "SELECT status, summary_json FROM lab_summary_review WHERE review_id=?", (REVIEW_ID,)).fetchone()


def test_pending_list_shows_the_original_summary(tmp_path):
    path = tmp_path / "review.sqlite3"
    _seed(path)
    listed = list_reviews(path)
    with sqlite3.connect(path) as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "lab_summary_decision" not in tables
    case = read_review(path, REVIEW_ID)
    assert listed[0]["decision"] is None and listed[0]["status"] == "pending"
    assert case["sources"][0]["id"] == "MHS-RES-001"
    assert case["summary"] == SUMMARY
    assert "follow_up_review_cases" not in Path(
        "app/clinical_lab_summary/review.py").read_text(encoding="utf-8")


def test_only_a_human_reviewer_can_approve_once(tmp_path):
    path = tmp_path / "review.sqlite3"
    _seed(path)
    before = _original(path)
    with pytest.raises(ReviewError) as unprepared:
        decide(path, REVIEW_ID, _reviewer(), "approved", "visto", WHEN)
    assert unprepared.value.reason == "schema_unprepared"
    prepare_decision_store(path)
    with pytest.raises(ReviewError) as agent:
        Reviewer("synthetic-executor", DEVELOPMENT_AUTHENTICATOR_V1, "session-1")
    assert agent.value.reason == "reviewer_denied"
    with pytest.raises(ReviewError) as forged:
        decide(path, REVIEW_ID, {"principal_id": "lab-reviewer"}, "approved", "visto", WHEN)
    assert forged.value.reason == "reviewer_denied"
    saved = decide(path, REVIEW_ID, _reviewer(), "approved", "Cifra sintetica coherente.", WHEN)
    assert saved["decision"]["decision"] == "approved"
    assert saved["decision"]["reviewer_id"] == "lab-reviewer"
    assert saved["decision_audit"] == [{
        "event": "decided", "outcome": "recorded", "actor_id": "lab-reviewer", "decision": "approved",
    }]
    assert _original(path) == before
    with pytest.raises(ReviewError) as second:
        decide(path, REVIEW_ID, _reviewer("other-reviewer"), "rejected", "otra lectura", WHEN)
    assert second.value.reason == "already_decided"
    assert _original(path) == before


def test_rejection_persists_after_reopen(tmp_path):
    path = tmp_path / "review.sqlite3"
    _seed(path)
    prepare_decision_store(path)
    decide(path, REVIEW_ID, _reviewer(), "rejected", "Falta contexto.", WHEN)
    reopened = read_review(path, REVIEW_ID)
    assert reopened["decision"]["decision"] == "rejected"
    assert reopened["status"] == "pending"
    assert reopened["summary"]["statements"][0]["text"] == "Hemoglobina 13.4 g/dL"


def test_concurrent_decisions_leave_one_row(tmp_path):
    path = tmp_path / "review.sqlite3"
    _seed(path)
    prepare_decision_store(path)
    before = _original(path)
    results = []

    def attempt(note):
        try:
            decide(path, REVIEW_ID, _reviewer(), "approved", note, WHEN)
            results.append("recorded")
        except ReviewError as error:
            results.append(error.reason)

    first = threading.Thread(target=attempt, args=("primera",))
    second = threading.Thread(target=attempt, args=("segunda",))
    first.start()
    second.start()
    first.join()
    second.join()
    assert sorted(results) == ["already_decided", "recorded"]
    assert _original(path) == before
    with sqlite3.connect(path) as connection:
        count = connection.execute("SELECT count(*) FROM lab_summary_decision").fetchone()[0]
    assert count == 1


def test_receipt_stays_attached_to_the_real_authorization(tmp_path):
    path = tmp_path / "review.sqlite3"
    _seed(path)
    receipt = {
        "operation_id": "lab-result-summary-v1", "provider": "gemini",
        "model": "gemini-3.5-flash-lite", "phase": "PENDING_REVIEW",
        "requests_sent": 1, "input_tokens": 169, "output_tokens": 107,
        "estimated_microusd": 319, "provider_request_id": "req-synthetic",
    }
    (tmp_path / "receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
    case = read_review(path, REVIEW_ID)
    assert case["receipt"]["provider"] == "gemini"
    assert case["receipt"]["requests_sent"] == 1
    assert "GEMINI_API_KEY" not in json.dumps(case["receipt"])


def test_http_rejects_a_browser_role_and_records_one_decision(tmp_path):
    path = tmp_path / "review.sqlite3"
    _seed(path)
    prepare_decision_store(path)
    before = _original(path)
    settings = Settings(
        model_boundary_base_url="http://model-boundary.test",
        model_boundary_path="/api/model-boundary/v1",
        model_boundary_timeout_seconds=5,
        model_boundary_service_token="synthetic-service-token-a",
        human_review_form_signing_secret="synthetic-form-signing-secret-b",
        host="127.0.0.1",
        port=8090,
        ai_review_db_path=str(tmp_path / "follow-up.sqlite3"),
        institutional_knowledge_db_path=str(tmp_path / "knowledge.sqlite3"),
        human_session_db_path=str(tmp_path / "human-session.sqlite3"),
        human_review_development_auth_enabled=True,
        human_review_development_auth_secret="development-secret-value-32chars-min",
        human_review_development_principal_id="lab-reviewer",
        human_review_development_principal_display_name="Lab reviewer",
        lab_summary_review_db_path=str(path),
    )
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        client = TestClient(app, base_url="http://127.0.0.1")
        hidden = client.get("/lab-summaries", follow_redirects=False)
        assert hidden.status_code in {302, 303, 307}
        logged = client.post(
            "/review-login",
            content=b"developmentSecret=development-secret-value-32chars-min",
            headers={"content-type": "application/x-www-form-urlencoded", **ORIGIN},
            follow_redirects=False)
        assert logged.status_code == 303
        client.cookies.set(SESSION_COOKIE, logged.headers["set-cookie"].split(";", 1)[0].split("=", 1)[1])
        page = client.get("/lab-summaries/" + REVIEW_ID)
        assert page.status_code == 200
        assert "Hemoglobina 13.4 g/dL" in page.text
        assert "MHS-RES-001" in page.text
        assert "Aprobar" in page.text and "Rechazar" in page.text
        forged = client.post(
            "/lab-summaries/" + REVIEW_ID + "/decision",
            content="decision=approved&note=ok&role=clinician".encode(),
            headers={"content-type": "application/x-www-form-urlencoded", **ORIGIN})
        assert forged.status_code == 422
        accepted = client.post(
            "/lab-summaries/" + REVIEW_ID + "/decision",
            content="decision=approved&note=Cifra%20sintetica".encode(),
            headers={"content-type": "application/x-www-form-urlencoded", **ORIGIN},
            follow_redirects=False)
        assert accepted.status_code == 303
        confirmed = client.get("/lab-summaries/" + REVIEW_ID)
        assert "approved" in confirmed.text and "lab-reviewer" in confirmed.text
        again = client.post(
            "/lab-summaries/" + REVIEW_ID + "/decision",
            content="decision=rejected&note=tarde".encode(),
            headers={"content-type": "application/x-www-form-urlencoded", **ORIGIN})
        assert again.status_code == 409
        assert _original(path) == before
        assert "Confirmo esta decisión" in page.text
        assert "No es autenticación clínica de producción" in page.text
    finally:
        app.dependency_overrides.clear()


def test_dashboard_filters_persisted_rows_and_does_not_parse_quantities(tmp_path):
    path = tmp_path / "review.sqlite3"
    summary = {
        "kind": "lab-result-summary-v1",
        "review": "pending_human_review",
        "statements": [{
            "text": "GLU 141 mmol/L",
            "sources": [
                {"source": "mini-lis", "resourceType": "Observation", "id": "MLS-RES-OLD"},
                {
                    "source": "mini-lis", "resourceType": "Observation", "id": "MLS-RES-UNCODED",
                    "value": 141, "unit": "mmol/L",
                },
                {
                    "source": "mini-his", "resourceType": "Observation", "id": "MHS-RES-001",
                    "system": "http://unitsofmeasure.org", "code": "g/dL", "unit": "g/dL",
                    "value": 13.4, "range_low": 12, "range_high": 16,
                },
            ],
        }],
    }
    queue_summary(path, REVIEW_ID, "e2e-clinical-001-gemini", "MHS-PAT-001", summary)
    other = "11111111-1111-4111-8111-111111111111"
    queue_summary(path, other, "lab-other", "MHS-PAT-002", SUMMARY)
    prepare_decision_store(path)
    decide(path, other, _reviewer(), "approved", "Registro sintético.", WHEN)
    settings = Settings(
        model_boundary_base_url="http://model-boundary.test",
        model_boundary_path="/api/model-boundary/v1",
        model_boundary_timeout_seconds=5,
        model_boundary_service_token="synthetic-service-token-a",
        human_review_form_signing_secret="synthetic-form-signing-secret-b",
        host="127.0.0.1",
        port=8090,
        ai_review_db_path=str(tmp_path / "follow-up.sqlite3"),
        institutional_knowledge_db_path=str(tmp_path / "knowledge.sqlite3"),
        human_session_db_path=str(tmp_path / "human-session.sqlite3"),
        human_review_development_auth_enabled=True,
        human_review_development_auth_secret="development-secret-value-32chars-min",
        human_review_development_principal_id="lab-reviewer",
        human_review_development_principal_display_name="Lab reviewer",
        lab_summary_review_db_path=str(path),
    )
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        client = TestClient(app, base_url="http://127.0.0.1")
        logged = client.post(
            "/review-login",
            content=b"developmentSecret=development-secret-value-32chars-min",
            headers={"content-type": "application/x-www-form-urlencoded", **ORIGIN},
            follow_redirects=False)
        client.cookies.set(SESSION_COOKIE, logged.headers["set-cookie"].split(";", 1)[0].split("=", 1)[1])
        page = client.get("/lab-summaries")
        assert page.status_code == 200
        assert ">1<" in page.text or page.text.count("<strong>1</strong>") == 2
        assert page.text.count("<strong>1</strong>") >= 2
        assert page.text.count("<strong>0</strong>") == 1
        pending = client.get("/lab-summaries?estado=pending&q=MHS-PAT-002")
        assert "Ningún resumen coincide" in pending.text
        assert "/lab-summaries/" + other not in pending.text
        detail = client.get("/lab-summaries/" + REVIEW_ID)
        assert "GLU 141 mmol/L" in detail.text
        assert "texto histórico generado por el modelo" in detail.text
        assert "no está semánticamente validada" in detail.text
        assert "Dato ausente" in detail.text
        assert "Unidad no verificable" in detail.text
        assert "No registrado" in detail.text
        assert "70-110" not in detail.text
        assert "mini-lis" in detail.text and "MLS-RES-OLD" in detail.text
        assert "MLS-RES-UNCODED" in detail.text and "mmol/L" in detail.text
        assert "13.4" in detail.text and "g/dL" in detail.text and "12–16 g/dL" in detail.text
        assert "UCUM verificable" in detail.text
    finally:
        app.dependency_overrides.clear()
