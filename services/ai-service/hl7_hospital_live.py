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
        authorization_id = os.environ.get("HL7_AUTHORIZATION_ID", "hl7-002-hospital")
        _permit(lab, authorization_id)
        federation = ClinicalFederationClient(
            os.environ["HL7_FEDERATION_URL"],
            os.environ["HL7_FEDERATION_TOKEN"],
            organization_id="org-mini-his",
            patient_system_key="mini-his",
            patient_identifier_system="https://lab.local/mini-his/patient",
            sources=("mini-his", "mini-lis"),
            timeout_seconds=20)
        gemini = _intercepted(sends)
        consent = _clinical_consent(lab, authorization_id, gemini)
        graph = _graph(lab, federation, review)
        state = graph.invoke(lab.executor["ORG-A"], authorization_id, 1000, PATIENT, consent)
        replay = graph.invoke(lab.executor["ORG-A"], authorization_id, 1000, PATIENT, consent)
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
        current_ids = {his_observation, lis_observation}
        current_cited, historical_cited = _classified(report["summary"], current_ids)
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
            "current_cited": current_cited,
            "historical_cited": historical_cited,
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
        current_ids = {os.environ["HL7_HIS_OBSERVATION_ID"], os.environ["HL7_LIS_OBSERVATION_ID"]}
        current = [fact for fact in observations if fact["id"] in current_ids]
        historical = [fact for fact in observations if fact["id"] not in current_ids]
        statements = [_statement(fact, "Resultado vigente.") for fact in current]
        for start in range(0, len(historical), 4):
            statements.append(_historical(historical[start:start + 4]))
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


def _statement(fact, prefix):
    return {
        "text": prefix + " " + fact["code"] + " " + fact["value"] + " " + fact["unit"],
        "sources": [{
            "source": fact["source"],
            "resourceType": "Observation",
            "id": fact["id"],
        }],
    }


def _historical(facts):
    body = "; ".join(fact["id"] + " " + fact["code"] + " " + fact["value"] + " " + fact["unit"] for fact in facts)
    return {
        "text": "Observacion historica sintetica, distinta de esta orden. " + body,
        "sources": [{
            "source": fact["source"],
            "resourceType": "Observation",
            "id": fact["id"],
        } for fact in facts],
    }


def _classified(summary, current_ids):
    current_cited = []
    historical_cited = []
    for statement in summary["statements"]:
        ids = [item["id"] for item in statement["sources"]]
        text = statement["text"]
        if any(item in current_ids for item in ids) and any(item not in current_ids for item in ids):
            raise RuntimeError("historical_mixed_into_current")
        if all(item in current_ids for item in ids):
            if "historica" in text:
                raise RuntimeError("current_labeled_historical")
            current_cited.extend(ids)
        else:
            if "historica" not in text:
                raise RuntimeError("historical_attributed_to_case")
            historical_cited.extend(ids)
    if not current_ids.issubset(set(current_cited)):
        raise RuntimeError("current_result_missing")
    return sorted(set(current_cited)), sorted(set(historical_cited))


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
