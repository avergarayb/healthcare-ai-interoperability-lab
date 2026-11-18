"""One hospital summary against a live federation. The provider hop stays intercepted.

This runner is invoked by the Java HL7 hospital test. It is not a pytest module.
"""
import json
import os
import sqlite3
import sys
from pathlib import Path

import httpx

from app.clinical_federation_client import ClinicalFederationClient
from app.clinical_lab_summary.review import ReviewError, Reviewer, decide, list_reviews, prepare_decision_store, read_review
from app.human_session import DEVELOPMENT_AUTHENTICATOR_V1
from tests.test_lab_summary import PATIENT, _clinical_consent, _graph, _open_clinical, _permit
from tests.test_model_gateway_durable_authorization import _ready
from tests.test_model_gateway_egress_gemini import _body


def main():
    ledger = Path(os.environ["HL7_LEDGER_DIR"]).resolve()
    review = Path(os.environ["HL7_REVIEW_DB"]).resolve()
    lis_observation = os.environ["HL7_LIS_OBSERVATION_ID"]
    his_observation = os.environ["HL7_HIS_OBSERVATION_ID"]
    lab = _ready(ledger)
    sends = []
    try:
        _open_clinical(lab)
        _permit(lab, "hl7-002-hospital")
        federation = ClinicalFederationClient(
            os.environ["HL7_FEDERATION_URL"],
            os.environ["HL7_FEDERATION_TOKEN"],
            organization_id="org-mini-his",
            patient_system_key="mini-his",
            patient_identifier_system="https://lab.local/mini-his/patient",
            sources=("mini-his", "mini-lis"),
            timeout_seconds=20)
        gemini = _intercepted(sends)
        consent = _clinical_consent(lab, "hl7-002-hospital", gemini)
        graph = _graph(lab, federation, review)
        state = graph.invoke(lab.executor["ORG-A"], "hl7-002-hospital", 1000, PATIENT, consent)
        replay = graph.invoke(lab.executor["ORG-A"], "hl7-002-hospital", 1000, PATIENT, consent)
        stored = list_reviews(review)
        if len(stored) != 1:
            raise RuntimeError("review_count")
        review_id = stored[0]["review_id"]
        prepare_decision_store(review)
        reviewer = Reviewer("hl7-reviewer", DEVELOPMENT_AUTHENTICATOR_V1, "session-hl7-002")
        decided = decide(
            review, review_id, reviewer, "approved",
            "Sintetico HL7-002 org-mini-his verificado.", "2026-11-18T03:00:00.000000Z")
        second = "accepted"
        try:
            decide(
                review, review_id, reviewer, "rejected",
                "Segundo intento sintetico.", "2026-11-18T03:05:00.000000Z")
        except ReviewError as error:
            second = str(error)
        report = read_review(review, review_id)
        cited = {(item["source"], item["resourceType"], item["id"]) for item in report["sources"]}
        expected = {("mini-his", "Observation", his_observation), ("mini-lis", "Observation", lis_observation)}
        if not expected.issubset(cited):
            raise RuntimeError("cited_observations_missing")
        summary_text = json.dumps(report["summary"])
        if "MSH|" in summary_text or "OML^" in summary_text or "PID|" in summary_text:
            raise RuntimeError("hl7_in_review")
        with sqlite3.connect(lab.ledger.path) as connection:
            reservations = [row[0] for row in connection.execute(
                "SELECT status FROM aip_remote_execution_reservation")]
        payload = {
            "ok": True,
            "phase": state.get("phase"),
            "reason": state.get("reason"),
            "review_status": state.get("review_status"),
            "requests_sent": state.get("requests_sent"),
            "model_calls": graph.model_calls,
            "replay_reason": replay.get("reason"),
            "provider_hosts": sorted({item["host"] for item in sends}),
            "provider_calls": len(sends),
            "chart_ids": sends[0]["chart_ids"] if sends else [],
            "cited": sorted(list(cited)),
            "summary_status": report["status"],
            "decision": None if decided.get("decision") is None else decided["decision"]["decision"],
            "decision_audit": report["decision_audit"],
            "queued_audit": report["audit"],
            "second_decision": second,
            "reservations": reservations,
            "authorization_id": report["authorization_id"],
        }
        sys.stdout.write(json.dumps(payload, ensure_ascii=True) + "\n")
    finally:
        lab.close()


def _intercepted(sends):
    def handler(request):
        raw = request.content.decode("utf-8")
        if "MSH|" in raw or "OML^" in raw or "PID|" in raw or "OBX|" in raw:
            raise RuntimeError("hl7_in_model_request")
        chart = _chart(raw)
        observations = [fact for fact in chart["facts"] if fact["resourceType"] == "Observation"]
        statements = []
        for fact in observations:
            statements.append({
                "text": fact["code"] + " " + fact["value"] + " " + fact["unit"],
                "sources": [{
                    "source": fact["source"],
                    "resourceType": "Observation",
                    "id": fact["id"],
                }],
            })
        body = json.dumps({
            "kind": "lab-result-summary-v1",
            "review": "pending_human_review",
            "statements": statements,
        })
        sends.append({
            "host": request.url.host,
            "chart_ids": [fact["id"] for fact in chart["facts"]],
        })
        return httpx.Response(200, json=_body(body), request=request)

    return httpx.Client(transport=httpx.MockTransport(handler))


def _chart(raw):
    decoded = raw.replace('\\"', '"')
    marker = '{"operation_id":"lab-result-summary-v1"'
    start = decoded.find(marker)
    if start < 0:
        raise RuntimeError("chart_missing")
    chart, _end = json.JSONDecoder().raw_decode(decoded[start:])
    if chart.get("patient_id") != PATIENT or "facts" not in chart:
        raise RuntimeError("chart_rejected")
    return chart


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        sys.stdout.write(json.dumps({"ok": False, "error": type(error).__name__ + ":" + str(error)}) + "\n")
        raise
