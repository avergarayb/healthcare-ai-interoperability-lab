"""Explicit TASK 003 live check. Only owned IAM + AI processes; tokens stay in memory."""
from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

import lab
from oidc_harness import Http, Trust

PORT = 18392
POLICY_PORT = 18393
WORKSPACE = lab.ROOT.parents[1]
SERVICE = WORKSPACE / "services/ai-service"


def startup(directory, trust_file, label, port=PORT):
    lab.free_port(port)
    env = {k: v for k, v in os.environ.items() if k.upper() in {
        "PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "USERPROFILE", "COMSPEC", "PATHEXT"}}
    env.update(PYTHONDONTWRITEBYTECODE="1", AI_SERVICE_HOST="127.0.0.1", GEMINI_API_KEY="",
               FOLLOWUP_AGENT_ENABLED="false", LLM_EXPERIMENTAL_ENABLED="false",
               AI_REVIEW_DB_PATH=str(directory / "review.sqlite"),
               HUMAN_SESSION_DB_PATH=str(directory / "session.sqlite"),
               INSTITUTIONAL_KNOWLEDGE_DB_PATH=str(directory / "knowledge.sqlite"),
               SECURITY_AUDIT_DB_PATH=str(directory / "legacy-audit.sqlite"),
               MODEL_BOUNDARY_BASE_URL="http://127.0.0.1:9",
               OIDC_WORKLOAD_LAB_ENABLED="true", OIDC_WORKLOAD_TRUST_CONFIG_PATH=str(trust_file),
               OIDC_WORKLOAD_AUDIT_DB_PATH=str(directory / "oidc-audit.sqlite"))
    log = open(directory / (label + ".log"), "x", encoding="utf-8")
    process = subprocess.Popen([str(SERVICE / ".venv/Scripts/python.exe"), "-B", "-m", "uvicorn", "app.main:app",
                                "--app-dir", str(SERVICE), "--host", "127.0.0.1", "--port", str(port),
                                "--no-access-log", "--log-level", "warning"],
                               cwd=directory, env=env, stdout=log, stderr=log)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        for _ in range(60):
            if process.poll() is not None:
                raise lab.Denied("AI_startup_failed")
            try:
                with opener.open(f"http://127.0.0.1:{port}/health", timeout=1) as response:
                    if response.status == 200:
                        return process, log, opener
            except (OSError, urllib.error.URLError):
                pass
            time.sleep(1)
        raise lab.Denied("AI_startup_timeout")
    except BaseException:
        stop_process(process, log)
        raise


def stop_process(process, log):
    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()  # Only the recorded child, never an existing service.
            process.wait(timeout=10)
    if log is not None:
        log.close()


def check(opener, encoded, expected, name, results, path="/iam-lab/v1/workload-context", extra=None, port=PORT):
    headers = {} if encoded is None else {"Authorization": "Bearer " + encoded}
    headers.update(extra or {})
    request = urllib.request.Request(f"http://127.0.0.1:{port}" + path, headers=headers)
    try:
        with opener.open(request, timeout=15) as response:
            status = response.status
            data = json.loads(response.read(8192))
    except urllib.error.HTTPError as error:
        status, data = error.code, None
    if status != expected:
        raise lab.Denied("unexpected_HTTP_status_" + name)
    if status == 200:
        if (data.get("internal_principal_id") != "fixture-ai-workload" or data.get("organization_id") != "org-lab-a"
                or "external_subject" in data or data.get("effective_permissions") != ["iam.workload-context.read"]):
            raise lab.Denied("unexpected_context_projection")
    results.append({"case": name, "category": "live", "http_status": status, "result": "PASS"})


def run():
    directory = state = process = log = None
    results = []
    stage = "preparation"
    try:
        lab.free_port(POLICY_PORT)
        directory, state = lab.prepare(18090, 18190)
        print("run_id=" + state["run_id"], flush=True)
        lab.start(directory, state)
        http = Http(state["origin"])
        trust = Trust.load(http)
        secrets = lab.read(directory / "secrets.json")["clients"]
        tokens = {client: http.request(trust.issuer + "/protocol/openid-connect/token", {
            "grant_type": "client_credentials", "client_id": client, "client_secret": secret})["access_token"]
            for client, secret in secrets.items()}
        config = lab.read(SERVICE / "oidc-workload.example.json")
        config.update(provider_id="keycloak-lab", enabled=True, allow_http_loopback=True, issuer=trust.issuer,
                      discovery_url=trust.issuer + "/.well-known/openid-configuration",
                      expected_jwks_uri=trust.issuer + "/protocol/openid-connect/certs",
                      endpoint_allowlist=[trust.issuer + suffix for suffix in (
                          "/.well-known/openid-configuration", "/protocol/openid-connect/certs",
                          "/protocol/openid-connect/token", "/protocol/openid-connect/auth")])
        trust_file = directory / "python-trust.json"
        lab.save(trust_file, config)
        stage = "AI_initial_startup"
        process, log, opener = startup(directory, trust_file, "AI-allowed")
        stage = "AI_initial_cases"
        ai = tokens["lab-ai-workload"]
        check(opener, ai, 200, "AI_access_token", results)
        check(opener, tokens["lab-python-to-java"], 401, "Java_audience", results)
        check(opener, tokens["lab-unregistered-workload"], 401, "unregistered_workload", results)
        check(opener, None, 401, "missing_authorization", results)
        check(opener, ai, 401, "contradictory_legacy_credential", results, extra={"X-Service-Token": "synthetic-not-valid"})
        check(opener, ai, 401, "legacy_route_rejects_bearer", results, path="/internal/agent-context")
        # Use actual expiry from a cryptographically verified provider token.
        claims = trust.decode(ai, "healthcare-ai-api", required=["iss", "sub", "aud", "iat", "exp"])
        time.sleep(max(0, claims["exp"] - time.time() + 1))
        check(opener, ai, 401, "expired_actual_token", results)
        stage = "AI_initial_stop"
        stop_process(process, log)
        process = log = None
        config["bindings"][0]["permissions"] = []
        lab.save(trust_file, config)
        stage = "AI_policy_startup"
        process, log, opener = startup(directory, trust_file, "AI-policy-denied", POLICY_PORT)
        new_ai = http.request(trust.issuer + "/protocol/openid-connect/token", {
            "grant_type": "client_credentials", "client_id": "lab-ai-workload", "client_secret": secrets["lab-ai-workload"]})["access_token"]
        stage = "AI_policy_case"
        check(opener, new_ai, 403, "registered_workload_without_route_grant", results, port=POLICY_PORT)
        with sqlite3.connect(directory / "oidc-audit.sqlite") as connection:
            audit = connection.execute("SELECT outcome,reason_code,count(*) FROM oidc_workload_security_audit_v1 GROUP BY outcome,reason_code").fetchall()
        expected_reasons = {"access_granted", "audience_rejected", "binding_unknown", "credential_missing",
                            "credential_conflict", "token_expired", "policy_rejected"}
        if {row[1] for row in audit} != expected_reasons or sum(row[2] for row in audit) != 7:
            raise lab.Denied("unexpected_audit_evidence")
        evidence = {"run_id": state["run_id"], "cases": results, "audit_summary": audit,
                    "real_id_token": "NOT_REPEATED: TASK002 token was never persisted and is expired; synthetic rejection tested",
                    "services_started": ["owned Keycloak", "owned AI Service"], "java_hapi_calls": "none"}
        lab.save(directory / "python-resource-server-evidence.json", evidence)
        print("live_cases_passed=" + str(len(results)), flush=True)
    except Exception as error:
        if directory is not None:
            failure = {"stage": stage, "error_type": type(error).__name__, "completed_cases": results}
            if isinstance(error, lab.Denied):
                failure["reason"] = str(error)
            if isinstance(error, OSError):
                failure["windows_error_code"] = getattr(error, "winerror", None)
            lab.save(directory / "python-resource-server-failure.json", failure)
        raise
    finally:
        stop_process(process, log)
        if directory is not None and state is not None:
            lab.cleanup(directory, state)
            for port in (PORT, POLICY_PORT):
                with socket.socket() as probe:
                    probe.settimeout(0.2)
                    if probe.connect_ex(("127.0.0.1", port)) == 0:
                        raise lab.Denied("AI_listener_still_open")
            lab.free_port(18090)
            print("owned_AI_and_IAM_resources_cleaned", flush=True)


if __name__ == "__main__":
    try:
        run()
    except lab.Denied as error:
        print("DENIED: " + str(error), file=sys.stderr)  # Closed local codes, never upstream bodies.
        raise SystemExit(1)
    except Exception:
        print("DENIED: live_resource_server_check_failed; no raw exception or credentials published", file=sys.stderr)
        raise SystemExit(1)
