"""DEMO-001 and DEMO-003 operator for the hospital container network.

The model hop stays inside MockTransport. This file does not open a provider socket.
"""
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, "/app")

import httpx

import hl7_hospital_live


def _secret(name):
    with open("/run/secrets/" + name, encoding="utf-8") as handle:
        return handle.read().strip()


def _wait(url):
    last = "unreachable"
    for _ in range(40):
        try:
            response = httpx.get(url, timeout=2.0)
            if response.status_code < 500:
                return
            last = str(response.status_code)
        except Exception as error:
            last = type(error).__name__
        time.sleep(3)
    raise RuntimeError("service_unavailable:" + last)


def _get(url, token=None):
    headers = {}
    if token:
        headers["X-Service-Token"] = token
    response = httpx.get(url, headers=headers, timeout=20.0)
    if response.status_code < 200 or response.status_code > 299:
        raise RuntimeError("http_" + str(response.status_code))
    return response.json()


def _post(url, body, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-Service-Token"] = token
    response = httpx.post(url, headers=headers, content=body, timeout=20.0)
    if response.status_code < 200 or response.status_code > 299:
        raise RuntimeError("http_" + str(response.status_code))
    return response.json()


def _order(his, lis, his_token, lis_token, case_id):
    created = _post(his + "/lab-orders", json.dumps({
        "patientId": "MHS-PAT-001",
        "destinationSystemKey": "mini-lis",
        "testCode": "GLU",
        "testDescription": "Glucose",
        "requestedAt": "2026-11-17T15:00:00Z",
    }))
    order_id = created["orderId"]
    submitted = _post(his + "/lab-orders/" + order_id + "/submission", "")
    lis_order = submitted["destination"]["orderId"]
    recorded = _post(lis + "/orders/" + lis_order + "/results", json.dumps({
        "externalResultId": "EXT-" + case_id,
        "testCode": "GLU",
        "value": "90",
        "unit": "mg/dL",
        "referenceRange": "70-110",
        "resultedAt": "2026-11-17T16:00:00Z",
        "status": "FINAL",
    }), lis_token)
    return {
        "his_order_id": order_id,
        "lis_order_id": lis_order,
        "lis_observation_id": recorded["resultId"],
        "service_request": submitted.get("serviceRequest", {}).get("resourceType"),
    }


def _projection(federation, token, his_order, lis_order, lis_observation):
    report = _get(federation + "/api/exchange/v1/orders/" + his_order + "/report", token)
    diagnostic = report.get("diagnosticReport") or {}
    based_on = (diagnostic.get("basedOn") or [{}])[0].get("reference")
    result = (diagnostic.get("result") or [{}])[0].get("reference")
    projection = {
        "service_request_id": (report.get("serviceRequest") or {}).get("id"),
        "diagnostic_report_id": diagnostic.get("id"),
        "based_on": based_on,
        "result": result,
    }
    expected = {
        "service_request_id": his_order,
        "diagnostic_report_id": lis_order,
        "based_on": "ServiceRequest/" + lis_order,
        "result": "Observation/" + lis_observation,
    }
    if projection != expected or "MSH|" in json.dumps(report):
        raise RuntimeError("fhir_projection_mismatch")
    return projection


def _federation(url, token, organization, case_id):
    response = httpx.post(
        url + "/api/clinical-federation/v1/context",
        headers={"Content-Type": "application/json", "X-Service-Token": token},
        content=json.dumps({
            "requestingOrganizationId": organization,
            "patient": {
                "systemKey": "mini-his",
                "identifierSystem": "https://lab.local/mini-his/patient",
                "identifierValue": "MHS-PAT-001",
            },
            "sources": ["mini-his", "mini-lis"],
            "resourceTypes": ["Patient", "Observation", "ServiceRequest", "DiagnosticReport"],
            "correlationId": "FED-" + case_id,
        }),
        timeout=20.0)
    body = {}
    try:
        body = response.json()
    except Exception:
        body = {}
    return response.status_code, body.get("status"), body.get("correlationId", "FED-" + case_id)


def main():
    his = os.environ["CATALOG_HIS_URL"]
    lis = os.environ["CATALOG_LIS_URL"]
    federation = os.environ["CATALOG_FEDERATION_URL"]
    case_id = os.environ.get("CATALOG_CASE_ID", "catalog-case-001")
    negative = os.environ.get("CATALOG_NEGATIVE", "")
    his_token = _secret("his_token")
    lis_token = _secret("lis_token")
    federation_token = _secret("federation_token")
    _wait(federation + "/actuator/health")
    _wait(his + "/actuator/health")
    if negative == "lis-down":
        try:
            httpx.get(lis + "/actuator/health", timeout=2.0)
            print(json.dumps({"demo": "DEMO-003", "negative": "lis-down", "result": "FAIL"}))
        except Exception:
            print(json.dumps({"demo": "DEMO-003", "negative": "lis-down", "result": "PASS"}))
        return
    if negative == "wrong-org":
        status, outcome, correlation = _federation(federation, federation_token, "org-other", case_id)
        denied = status >= 400 or outcome not in {"complete"}
        print(json.dumps({
            "demo": "DEMO-003",
            "negative": "wrong-org",
            "http": status,
            "federation_status": outcome,
            "correlation_id": correlation,
            "result": "PASS" if denied else "FAIL",
        }))
        return
    if negative == "bad-secret":
        response = httpx.post(
            federation + "/api/clinical-federation/v1/context",
            headers={"Content-Type": "application/json", "X-Service-Token": "not-the-secret"},
            content="{}",
            timeout=20.0)
        print(json.dumps({
            "demo": "DEMO-003",
            "negative": "bad-secret",
            "http": response.status_code,
            "result": "PASS" if response.status_code in {401, 403} else "FAIL",
        }))
        return
    evidence = _order(his, lis, his_token, lis_token, case_id)
    projection = _projection(
        federation, his_token, evidence["his_order_id"], evidence["lis_order_id"], evidence["lis_observation_id"])
    status, outcome, correlation = _federation(federation, federation_token, "org-mini-his", case_id)
    ledger = Path("/var/lab/ledger") / case_id
    ledger.mkdir(parents=True, exist_ok=True)
    Path("/var/lab/review").mkdir(parents=True, exist_ok=True)
    os.environ["HL7_LEDGER_DIR"] = str(ledger)
    os.environ["HL7_REVIEW_DB"] = "/var/lab/review/" + case_id + ".sqlite3"
    os.environ["HL7_FEDERATION_URL"] = federation
    os.environ["HL7_FEDERATION_TOKEN"] = federation_token
    os.environ["HL7_HIS_OBSERVATION_ID"] = "MHS-RES-001"
    os.environ["HL7_LIS_OBSERVATION_ID"] = evidence["lis_observation_id"]
    os.environ["HL7_AUTHORIZATION_ID"] = "catalog-summary-" + case_id
    print(json.dumps({
        "demo": "DEMO-003",
        "organization": "org-mini-his",
        "patient": "MHS-PAT-001",
        "federation_http": status,
        "federation_status": outcome,
        "correlation_id": correlation,
        **evidence,
        "fhir": projection,
        "result": "PASS" if status == 200 and outcome == "complete" else "FAIL",
    }))
    print(json.dumps({"demo": "DEMO-001", "provider_transport": "intercepted_simulation", "provider_socket": False}))
    hl7_hospital_live.main()
    if negative == "consumed":
        try:
            hl7_hospital_live.main()
            print(json.dumps({"demo": "DEMO-001", "negative": "consumed", "result": "FAIL"}))
        except Exception as error:
            closed = type(error).__name__ in {"ExecutionError", "RuntimeError"}
            print(json.dumps({
                "demo": "DEMO-001",
                "negative": "same_case_reopen",
                "error": type(error).__name__,
                "result": "PASS" if closed else "FAIL",
            }))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(json.dumps({"ok": False, "error": type(error).__name__ + ":" + str(error), "result": "FAIL"}))
        raise
