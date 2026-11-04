"""TASK 005 opt-in: owned Keycloak + isolated Java only. Tokens remain in memory."""
from __future__ import annotations

import http.client as http_client
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
from contextlib import closing

import lab
from oidc_harness import Http, Trust

SERVICE = lab.ROOT.parents[1] / "services/fhir-integration-service"
JAR = SERVICE / "target/fhir-integration-service-0.0.1-SNAPSHOT.jar"
PORTS = (18396, 18397, 18398, 18399)
ROUTE = "/iam-lab/v1/workload-context"


def stop(process, output):
    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()  # Only this recorded child.
            process.wait(timeout=10)
    if output is not None:
        output.close()


def start(directory, label, port, config=None):
    lab.free_port(port)
    working = directory / label
    working.mkdir(exist_ok=False)
    if any((p / ".env").exists() for p in (working, working.parent, working.parent.parent)):
        raise lab.Denied("inherited_dotenv_refused")
    environment = {k: v for k, v in os.environ.items() if k.upper() in {
        "PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "USERPROFILE", "JAVA_HOME", "COMSPEC", "PATHEXT"}}
    if config is not None:
        environment.update(IAM_JAVA_WORKLOAD_TRUST_CONFIG_PATH=str(config),
                           IAM_JAVA_WORKLOAD_AUDIT_DB_PATH=str(directory / "java-oidc-audit.sqlite"))
    arguments = ["java", "-jar", str(JAR), "--server.address=127.0.0.1", f"--server.port={port}",
                 "--spring.main.banner-mode=off", "--logging.level.root=WARN",
                 "--logging.level.org.springframework=WARN", "--logging.level.org.springframework.security=WARN",
                 f"--exchange.store-path={working / 'exchange.sqlite'}",
                 f"--federation.security-audit.store-path={working / 'federation-audit.sqlite'}"]
    if config is not None:
        arguments.append("--iam.java.workload.lab.enabled=true")
    output = open(working / "server.log", "x", encoding="utf-8")
    process = subprocess.Popen(arguments, cwd=working, env=environment, stdout=output, stderr=output)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        for _ in range(60):
            if process.poll() is not None:
                raise lab.Denied("owned_Java_startup_failed")
            try:
                with opener.open(f"http://127.0.0.1:{port}/actuator/health/liveness", timeout=1) as response:
                    if response.status == 200:
                        return process, output, opener
            except (OSError, urllib.error.URLError):
                pass
            time.sleep(1)
        raise lab.Denied("owned_Java_startup_timeout")
    except BaseException:
        stop(process, output)
        raise


def check(opener, port, name, expected, results, *, token=None, path=ROUTE, method="GET", extra=None,
          category="live_provider_oidc"):
    headers = {} if token is None else {"Authorization": "Bearer " + token}
    headers.update(extra or {})
    request = urllib.request.Request(f"http://127.0.0.1:{port}" + path, headers=headers, method=method)
    try:
        with opener.open(request, timeout=15) as response:
            status, body = response.status, response.read(16384)
    except urllib.error.HTTPError as error:
        status, body = error.code, b""
        error.close()
    if status != expected:
        raise lab.Denied("unexpected_Java_HTTP_" + name)
    if status == 200 and path == ROUTE:
        value = json.loads(body)
        if (value.get("internal_principal_id") != "fixture-python-to-java"
                or value.get("organization_id") != "org-lab-b"
                or value.get("audience") != "healthcare-interop-api"
                or value.get("effective_permissions") != ["iam.java-workload-context.read"]
                or any(k in value for k in ("provider_id", "external_issuer", "external_subject", "token"))):
            raise lab.Denied("unexpected_Java_context")
    results.append({"case": name, "category": category, "http_status": status, "result": "PASS"})


def check_duplicate(port, encoded, results):
    with closing(http_client.HTTPConnection("127.0.0.1", port, timeout=15)) as connection:
        connection.putrequest("GET", ROUTE)
        connection.putheader("Authorization", "Bearer " + encoded)
        connection.putheader("Authorization", "Bearer " + encoded)
        connection.endheaders()
        response = connection.getresponse()
        if response.status != 401:
            raise lab.Denied("duplicate_Java_Authorization_not_rejected")
        response.read(8192)
    results.append({"case": "duplicate_authorization", "category": "live_provider_oidc", "http_status": 401, "result": "PASS"})


def run():
    directory = state = process = output = None
    stage, results = "preparation", []
    try:
        if not JAR.is_file():
            raise lab.Denied("current_Java_package_required")
        for port in PORTS:
            lab.free_port(port)
        directory, state = lab.prepare(18090, 18190)
        print("run_id=" + state["run_id"], flush=True)
        stage = "disabled_Java_without_provider"
        process, output, opener = start(directory, "java-disabled", PORTS[0])
        check(opener, PORTS[0], "disabled_liveness", 200, results, path="/actuator/health/liveness", category="runtime_without_provider")
        check(opener, PORTS[0], "disabled_route_absent", 404, results, category="runtime_without_provider")
        legacy = [("GET", "/api/model-boundary/v1"), ("GET", "/api/clinical-read/v1/patients/synthetic-not-read"),
                  ("POST", "/api/clinical-federation/v1/context"), ("POST", "/api/exchange/v1/orders")]
        for index, (method, path) in enumerate(legacy):
            check(opener, PORTS[0], "disabled_legacy_gate_" + str(index), 401, results,
                  path=path, method=method, category="runtime_without_provider")
        lab.free_port(18090)  # No provider was running during those six checks.
        stop(process, output)
        process = output = None
        stage = "owned_Keycloak_startup"
        lab.start(directory, state)
        http = Http(state["origin"])
        trust = Trust.load(http)
        clients = lab.read(directory / "secrets.json")["clients"]
        config = lab.read(SERVICE / "java-oidc-workload.example.json")
        config.update(provider_id="keycloak-lab", enabled=True, allow_http_loopback=True, issuer=trust.issuer,
                      discovery_url=trust.issuer + "/.well-known/openid-configuration",
                      expected_jwks_uri=trust.issuer + "/protocol/openid-connect/certs",
                      endpoint_allowlist=[trust.issuer + suffix for suffix in (
                          "/.well-known/openid-configuration", "/protocol/openid-connect/certs",
                          "/protocol/openid-connect/token", "/protocol/openid-connect/auth")])
        def issued(client):
            return http.request(trust.issuer + "/protocol/openid-connect/token", {
                "grant_type": "client_credentials", "client_id": client, "client_secret": clients[client]})["access_token"]
        config_file = directory / "java-trust.json"
        lab.save(config_file, config)
        stage = "enabled_Java_startup"
        process, output, opener = start(directory, "java-allowed", PORTS[1], config_file)
        java_token, ai_token = issued("lab-python-to-java"), issued("lab-ai-workload")
        java_claims = trust.decode(java_token, "healthcare-interop-api", required=["iss", "sub", "aud", "iat", "exp"])
        trust.decode(ai_token, "healthcare-ai-api", required=["iss", "sub", "aud", "iat", "exp"])
        stage = "real_Java_API_controls"
        check(opener, PORTS[1], "registered_Java_workload", 200, results, token=java_token)
        check(opener, PORTS[1], "AI_audience_rejected_by_Java", 401, results, token=ai_token)
        check(opener, PORTS[1], "missing_authorization", 401, results)
        check(opener, PORTS[1], "contradictory_legacy_credential", 401, results, token=java_token,
              extra={"X-Service-Token": "synthetic-invalid"})
        check(opener, PORTS[1], "cookie_conflict", 401, results, token=java_token, extra={"Cookie": "lab=synthetic"})
        check(opener, PORTS[1], "malformed_authorization", 401, results, extra={"Authorization": "bearer malformed"})
        check_duplicate(PORTS[1], java_token, results)
        for index, (method, path) in enumerate(legacy):
            check(opener, PORTS[1], "enabled_legacy_rejects_bearer_" + str(index), 401, results,
                  token=java_token, path=path, method=method, category="legacy_isolation_with_provider_token")
        stage = "actual_Java_token_expiry"
        time.sleep(max(0, java_claims["exp"] - time.time() + 1))
        check(opener, PORTS[1], "expired_original_Java_token", 401, results, token=java_token)
        stop(process, output)
        process = output = None
        config["bindings"][0]["permissions"] = []
        denied = directory / "java-trust-denied.json"
        lab.save(denied, config)
        stage = "local_permission_denied"
        process, output, opener = start(directory, "java-policy-denied", PORTS[2], denied)
        check(opener, PORTS[2], "valid_Java_workload_without_permission", 403, results, token=issued("lab-python-to-java"))
        stop(process, output)
        process = output = None
        config["bindings"] = []
        unbound = directory / "java-trust-unbound.json"
        lab.save(unbound, config)
        stage = "real_target_audience_without_local_binding"
        process, output, opener = start(directory, "java-unbound", PORTS[3], unbound)
        check(opener, PORTS[3], "valid_Java_audience_without_local_binding", 401, results, token=issued("lab-python-to-java"))
        with closing(sqlite3.connect((directory / "java-oidc-audit.sqlite").as_uri() + "?mode=ro", uri=True)) as connection:
            audit = connection.execute("SELECT outcome,reason_code,count(*) FROM java_oidc_security_audit_v1 GROUP BY outcome,reason_code").fetchall()
        expected = {"access_granted": 1, "audience_rejected": 1, "credential_missing": 1, "credential_conflict": 2,
                    "credential_ambiguous": 1, "credential_malformed": 1, "token_expired": 1, "policy_rejected": 1, "binding_unknown": 1}
        if {r[1]: r[2] for r in audit} != expected or len(results) != 20:
            raise lab.Denied("Java_audit_evidence_mismatch")
        lab.save(directory / "java-resource-server-evidence.json", {
            "run_id": state["run_id"], "cases": results, "audit_summary": audit,
            "unknown_binding_case": "real lab-python-to-java Interop token; isolated Java registration intentionally empty",
            "real_human_ID_token": "not repeated; synthetic new-boundary rejection only",
            "storage_failure": "deterministic only; not live injected", "Keycloak_fixture_changed": False,
            "clinical_calls": "none", "python_product_service_started": False})
        print("Java_operational_controls_passed=" + str(len(results)), flush=True)
    except Exception as error:
        if directory is not None:
            failure = {"stage": stage, "error_type": type(error).__name__, "completed_cases": results}
            if isinstance(error, lab.Denied):
                failure["reason"] = str(error)
            lab.save(directory / "java-resource-server-failure.json", failure)
        raise
    finally:
        stop(process, output)
        if directory is not None and state is not None:
            lab.cleanup(directory, state)
            after = lab.inventory()
            preserved = all(set(after[k]) == set(state["baseline"][k]) for k in after)
            listeners_closed = True
            for port in PORTS:
                with socket.socket() as probe:
                    probe.settimeout(0.2)
                    listeners_closed &= probe.connect_ex(("127.0.0.1", port)) != 0
            cleaned = all(not (directory / name).exists() for name in lab.SECRET_FILES)
            lab.save(directory / "java-resource-server-cleanup.json", {
                "baseline_exactly_preserved": preserved, "Java_listeners_closed": listeners_closed,
                "ephemeral_secrets_removed": cleaned, "own_counts": {k: len(v) for k, v in state["owned"].items()},
                "baseline_counts": {k: len(v) for k, v in state["baseline"].items()},
                "final_counts": {k: len(v) for k, v in after.items()}, "HAPI_operations": "none"})
            if not all((preserved, listeners_closed, cleaned)):
                raise lab.Denied("Java_live_cleanup_incomplete")
            print("owned_Java_and_IAM_resources_cleaned", flush=True)


if __name__ == "__main__":
    try:
        run()
    except lab.Denied as error:
        print("DENIED: " + str(error), file=sys.stderr)
        raise SystemExit(1)
    except Exception:
        print("DENIED: Java_live_check_failed; inspect sanitized local evidence", file=sys.stderr)
        raise SystemExit(1)
