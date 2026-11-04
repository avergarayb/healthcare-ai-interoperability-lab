"""TASK 006 opt-in simultaneous IAM lab. No product imports or token persistence."""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import socket
import sqlite3
import sys
import time
import urllib.error
import urllib.request
import uuid

import lab
from oidc_harness import Http, NoRedirect, Trust
import verify_java_resource_server as java
import verify_python_resource_server as python
from verify_trusted_identity_registry import operate

PORTS = {"python": 18402, "java": 18403}
AUDIENCES = {"python": "healthcare-ai-api", "java": "healthcare-interop-api"}
PERMISSIONS = {"python": "iam.workload-context.read", "java": "iam.java-workload-context.read"}
ROUTE = "/iam-lab/v1/workload-context"
PROJECTIONS = {"context_version", "internal_principal_id", "organization_id", "principal_type",
               "authentication_method", "audience", "effective_permissions", "authenticated_at",
               "expires_at", "correlation_id"}
TABLES = {"python": "oidc_workload_security_audit_v1", "java": "java_oidc_security_audit_v1"}
LEGACY = {"python": [("GET", "/internal/agent-context")], "java": [
    ("GET", "/api/model-boundary/v1"), ("GET", "/api/clinical-read/v1/patients/synthetic-not-read"),
    ("POST", "/api/clinical-federation/v1/context"), ("POST", "/api/exchange/v1/orders")]}


class Inconclusive(Exception):
    """Expired during a non-expiry control; never counted as a policy PASS."""


@dataclass(frozen=True, repr=False)
class Token:
    encoded: str
    audience: str
    client: str
    expires: int
    issuance: int

    def current(self):
        if time.time() >= self.expires:
            raise Inconclusive()


def configured(example, issuer):
    value = lab.read(example)
    value.update(provider_id="keycloak-lab", enabled=True, issuer=issuer, allow_http_loopback=True,
                 discovery_url=issuer + "/.well-known/openid-configuration",
                 expected_jwks_uri=issuer + "/protocol/openid-connect/certs",
                 endpoint_allowlist=[issuer + suffix for suffix in (
                     "/.well-known/openid-configuration", "/protocol/openid-connect/certs",
                     "/protocol/openid-connect/token", "/protocol/openid-connect/auth")])
    return value


def projection(value, service, token, correlation):
    organization, principal = (("org-lab-a", "fixture-ai-workload") if service == "python"
                               else ("org-lab-b", "fixture-python-to-java"))
    if (not isinstance(value, dict) or set(value) != PROJECTIONS
            or value["context_version"] != "identity-principal-context-v1"
            or value["principal_type"] != "workload"
            or value["authentication_method"] != "oauth2_client_credentials"
            or value["internal_principal_id"] != principal or value["organization_id"] != organization
            or value["audience"] != AUDIENCES[service]
            or value["effective_permissions"] != [PERMISSIONS[service]]
            or value["correlation_id"] != correlation):
        raise lab.Denied("projection_contract_mismatch")
    try:
        authenticated = datetime.fromisoformat(value["authenticated_at"].replace("Z", "+00:00"))
        expiry = datetime.fromisoformat(value["expires_at"].replace("Z", "+00:00"))
        if (authenticated.utcoffset() is None or expiry.utcoffset() is None
                or not authenticated.timestamp() < expiry.timestamp() <= token.expires
                or expiry.timestamp() <= time.time()):
            raise ValueError()
    except (ValueError, TypeError, AttributeError, OverflowError):
        raise lab.Denied("projection_time_mismatch") from None


def read_audit(path, service, correlation=None):
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as connection:
        query = "SELECT outcome,reason_code,actor_type,actor_id,organization_id FROM " + TABLES[service]
        rows = connection.execute(query + (" WHERE correlation_id=?" if correlation else ""),
                                  (correlation,) if correlation else ()).fetchall()
    return rows


class Matrix:
    def __init__(self, directory, trust, http, clients, children):
        self.directory, self.trust, self.http, self.clients, self.children = directory, trust, http, clients, children
        self.results, self.issuances, self.sequence = [], [], 0
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def issue(self, client, audience):
        self.sequence += 1
        response = self.http.request(self.trust.issuer + "/protocol/openid-connect/token", {
            "grant_type": "client_credentials", "client_id": client, "client_secret": self.clients[client]})
        if response.get("token_type", "").lower() != "bearer" or "id_token" in response:
            raise lab.Denied("unexpected_token_response")
        encoded = response["access_token"]
        claims = self.trust.decode(encoded, audience, required=["iss", "sub", "aud", "iat", "exp", "typ", "azp", "jti"])
        actual_audiences = claims["aud"] if isinstance(claims["aud"], list) else [claims["aud"]]
        if (actual_audiences != [audience] or claims["typ"] != "Bearer" or claims["azp"] != client
                or not 0 < claims["exp"] - claims["iat"] <= 35):
            raise lab.Denied("fixture_token_profile_changed")
        token = Token(encoded, audience, client, claims["exp"], self.sequence)
        self.issuances.append({"issuance": token.issuance, "client": client, "audience": audience,
                               "grant": "client_credentials", "unchanged_provider_token": True})
        return token

    def check(self, service, name, expected, token=None, *, extra=None, malformed=False,
              reason=None, legacy=None, expired=False):
        if any(process.poll() is not None for process, _ in self.children):
            raise lab.Denied("owned_child_not_running")
        correlation = str(uuid.uuid4())
        headers = {"X-Correlation-ID": correlation}
        if token is not None:
            if expired:
                if time.time() <= token.expires:
                    raise lab.Denied("actual_expiry_required")
            else:
                token.current()
                self.trust.decode(token.encoded, token.audience, required=["iss", "sub", "aud", "iat", "exp"])
            headers["Authorization"] = "Bearer " + token.encoded
        if malformed:
            headers["Authorization"] = "bearer malformed"
        headers.update(extra or {})
        method, path = legacy or ("GET", ROUTE)
        if legacy is not None and legacy not in LEGACY[service]:
            raise lab.Denied("unapproved_test_route")
        request = urllib.request.Request(f"http://127.0.0.1:{PORTS[service]}" + path, headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=10) as response:
                status, raw = response.status, response.read(16385)
        except urllib.error.HTTPError as error:
            status, raw = error.code, error.read(16385)
            error.close()
        record = {"case": name, "service": service, "expected": expected, "observed": status,
                  "classification": "Live Keycloak" if token else "Integration HTTP (no token)",
                  "correlation_id": correlation, "issuance": None if token is None else token.issuance}
        if token is not None and not expired:
            try:
                token.current()
                self.trust.decode(token.encoded, token.audience, required=["iss", "sub", "aud", "iat", "exp"])
            except (Inconclusive, lab.Denied) as error:
                if isinstance(error, Inconclusive) or str(error) == "token_expired":
                    record["status"] = "INCONCLUSIVE"
                    self.results.append(record)
                    raise Inconclusive() from None
                raise
            record["token_valid_before_and_after"] = True
        if status != expected or len(raw) > 16384:
            raise lab.Denied("HTTP_matrix_mismatch_" + name)
        if expected == 200:
            projection(json.loads(raw), service, token, correlation)
        if legacy is None:
            audit = self.directory / ("python/oidc-audit.sqlite" if service == "python" else "java-oidc-audit.sqlite")
            rows = read_audit(audit, service, correlation)
            outcome = "allowed" if expected == 200 else "denied"
            if (len(rows) != 1 or rows[0][0] != outcome
                    or rows[0][2] != ("workload" if expected == 200 else "anonymous")
                    or (expected != 200 and rows[0][3:] != (None, None))
                    or (reason is not None and rows[0][1] != reason)):
                raise lab.Denied("persistent_audit_mismatch")
            record.update(audit_visible_at_response=True, audit_reason=rows[0][1])
        record["status"] = "PASS"
        self.results.append(record)

    def mutate(self, operation, permission=PERMISSIONS["python"]):
        result = operate(self.directory / "python", operation, "--target", "fixture-ai-workload",
                         "--organization", "org-lab-a", "--permission", permission,
                         "--operator-label", "synthetic-task006")
        if result.get("committed") is not True or result.get("operator_verified") is not False:
            raise lab.Denied("unverified_CLI_contract_changed")

    def execute(self):
        # Entire valid-token sequence retries as a unit, not an expiry denial relabeled as policy evidence.
        for attempt in range(2):
            start = len(self.results)
            self.mutate("grant-permission")
            self.mutate("revoke-permission", PERMISSIONS["java"])
            ai = self.issue("lab-ai-workload", AUDIENCES["python"])
            interop = self.issue("lab-python-to-java", AUDIENCES["java"])
            unknown = self.issue("lab-unregistered-workload", AUDIENCES["python"])
            try:
                self.check("python", "AI_own_audience", 200, ai)
                self.check("java", "same_AI_cross_audience", 401, ai, reason="audience_rejected")
                self.check("java", "Java_own_audience", 200, interop)
                self.check("python", "same_Java_cross_audience", 401, interop, reason="audience_rejected")
                self.check("python", "unregistered_AI_workload", 401, unknown, reason="binding_unknown")
                for service, token in (("python", ai), ("java", interop)):
                    self.check(service, "missing_credential", 401, reason="credential_missing")
                    self.check(service, "malformed_credential", 401, malformed=True, reason="credential_malformed")
                    self.check(service, "legacy_credential_conflict", 401, token,
                               extra={"X-Service-Token": "synthetic-not-valid"}, reason="credential_conflict")
                    self.check(service, "cookie_conflict", 401, token,
                               extra={"Cookie": "lab=synthetic"}, reason="credential_conflict")
                    self.check(service, "other_organization_not_membership", 403, token,
                               extra={"X-IAM-Lab-Organization": "org-lab-b" if service == "python" else "org-lab-a"},
                               reason="organization_rejected")
                    for index, route in enumerate(LEGACY[service]):
                        self.check(service, "legacy_rejects_Bearer_" + str(index), 401, token, legacy=route)
                self.check("python", "before_revocation_same_token", 200, ai)
                self.mutate("revoke-permission")
                self.check("python", "revoked_same_valid_token", 403, ai, reason="policy_rejected")
                self.check("java", "Java_unchanged_during_Python_revocation", 200, interop)
                self.mutate("grant-permission", PERMISSIONS["java"])
                self.check("python", "Java_permission_is_not_Python_permission", 403, ai, reason="policy_rejected")
                self.check("python", "local_grant_cannot_override_wrong_audience", 401, interop, reason="audience_rejected")
                self.mutate("grant-permission")
                self.check("python", "explicit_restore_same_valid_token", 200, ai)
                self.mutate("revoke-permission", PERMISSIONS["java"])
                self.check("java", "Java_unchanged_after_Python_restore", 200, interop)
                break
            except Inconclusive:
                for result in self.results[start:]:
                    result["status"] = "INCONCLUSIVE"
                if attempt == 1:
                    raise lab.Denied("inconclusive_after_bounded_reissuance") from None
        delay = max(ai.expires, interop.expires) - time.time() + 1
        if delay > 36:
            raise lab.Denied("unexpected_expiry_wait")
        time.sleep(max(0, delay))
        self.check("python", "actual_expired_original_AI_token", 401, ai, reason="token_expired", expired=True)
        self.check("java", "actual_expired_original_Java_token", 401, interop, reason="token_expired", expired=True)


def cleanup(directory, state, children):
    failures = []
    for process, log in reversed(children):
        try:
            java.stop(process, log)
        except Exception:
            failures.append("owned_child_stop_failed")
    try:
        lab.cleanup(directory, state)
    except Exception:
        failures.append("owned_IAM_cleanup_failed")
    after = lab.inventory()
    closed = True
    for port in (*PORTS.values(), state["port"]):
        with socket.socket() as probe:
            probe.settimeout(0.2)
            closed &= probe.connect_ex(("127.0.0.1", port)) != 0
    report = {"baseline_exactly_preserved": all(set(after[k]) == set(state["baseline"][k]) for k in after),
              "owned_resources_removed": all(not set(after[k]) & set(state["owned"][k]) for k in after),
              "listeners_closed": closed, "recorded_children_exited": all(p.poll() is not None for p, _ in children),
              "ephemeral_secrets_removed": all(not (directory / name).exists() for name in lab.SECRET_FILES),
              "own_counts": {k: len(v) for k, v in state["owned"].items()},
              "baseline_counts": {k: len(v) for k, v in state["baseline"].items()},
              "final_counts": {k: len(v) for k, v in after.items()}, "cleanup_errors": failures,
              "HAPI_operations": "none", "Mini_HIS_LIS_operations": "none"}
    lab.save(directory / "cross-service-cleanup.json", report)
    if failures or not all(report[key] for key in ("baseline_exactly_preserved", "owned_resources_removed",
            "listeners_closed", "recorded_children_exited", "ephemeral_secrets_removed")):
        raise lab.Denied("cross_service_cleanup_incomplete")


def run():
    directory = state = matrix = None
    children = []
    stage = "preparation"
    try:
        if not java.JAR.is_file():
            raise lab.Denied("current_Java_package_required")
        for port in PORTS.values():
            lab.free_port(port)
        directory, state = lab.prepare(18090, 18190)
        print("run_id=" + state["run_id"], flush=True)
        stage = "owned_Keycloak_startup"
        lab.start(directory, state)
        http = Http(state["origin"])
        trust = Trust.load(http)
        py_dir = directory / "python"
        py_dir.mkdir(exist_ok=False)
        if any((p / ".env").exists() for p in (py_dir, directory, directory.parent)):
            raise lab.Denied("inherited_dotenv_refused")
        py_config = configured(python.SERVICE / "oidc-workload.example.json", trust.issuer)
        py_config.update(bindings=[], allowed_organization_ids=["org-lab-a", "org-lab-b"])
        registry = lab.read(python.SERVICE / "trusted-identity-registry.example.json")
        registry.update(provider_id="keycloak-lab", issuer=trust.issuer)
        registry["bindings"][0]["issuer"] = trust.issuer
        fixture = py_dir / "registry-fixture.json"
        lab.save(fixture, registry)
        operate(py_dir, "init", "--fixture", str(fixture), "--operator-label", "synthetic-task006")
        py_file, java_file = py_dir / "trust.json", directory / "java-trust.json"
        lab.save(py_file, py_config)
        lab.save(java_file, configured(java.SERVICE / "java-oidc-workload.example.json", trust.issuer))
        java_hash = hashlib.sha256(java_file.read_bytes()).hexdigest()
        stage = "both_product_startups_before_token_issuance"
        process, log, _ = python.startup(py_dir, py_file, "AI", PORTS["python"], registry_path=py_dir / "identity-registry.sqlite")
        children.append((process, log))
        process, log, _ = java.start(directory, "java", PORTS["java"], java_file)
        children.append((process, log))
        matrix = Matrix(directory, trust, http, lab.read(directory / "secrets.json")["clients"], children)
        stage = "simultaneous_live_matrix"
        matrix.execute()
        if hashlib.sha256(java_file.read_bytes()).hexdigest() != java_hash:
            raise lab.Denied("Java_static_configuration_changed")
        summaries = {}
        for service, path in (("python", py_dir / "oidc-audit.sqlite"), ("java", directory / "java-oidc-audit.sqlite")):
            rows = read_audit(path, service)
            counts = {}
            for outcome, reason, *_ in rows:
                key = outcome + ":" + reason
                counts[key] = counts.get(key, 0) + 1
            summaries[service] = {"events": len(rows), "outcome_reasons": counts}
        with closing(sqlite3.connect((py_dir / "identity-registry.sqlite").as_uri() + "?mode=ro", uri=True)) as connection:
            changes = connection.execute("SELECT revision,operation,operator_verified FROM registry_policy_change_audit ORDER BY revision").fetchall()
        if not any(operation == "revoke-permission" for _, operation, _ in changes) or any(verified for _, _, verified in changes):
            raise lab.Denied("registry_change_evidence_missing")
        for path in (py_dir / "AI.log", directory / "java/server.log"):
            content = path.read_text(encoding="utf-8")
            if (trust.issuer in content or any(secret in content for secret in matrix.clients.values())
                    or re.search(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+|Bearer |Using generated security password", content)):
                raise lab.Denied("owned_log_disclosure")
        lab.save(directory / "cross-service-evidence.json", {"run_id": state["run_id"], "cases": matrix.results,
            "issuances": matrix.issuances, "audit_summary": summaries, "registry_changes": changes,
            "same_exact_approved_issuer": True, "both_services_ready_before_tokens": True,
            "Java_static_policy_unchanged": True, "independent_audit_stores": True,
            "provider_lifetime_unchanged": True, "ports": PORTS,
            "tokens_persisted": False, "clinical_calls": "none",
            "audit_failure_and_role_injection": "deterministic suites only, not live injection"})
        print("cross_service_controls_passed=" + str(sum(row["status"] == "PASS" for row in matrix.results)), flush=True)
    except Exception as error:
        if directory is not None:
            lab.save(directory / "cross-service-failure.json", {"stage": stage, "error_type": type(error).__name__,
                "completed_cases": [] if matrix is None else matrix.results})
        raise
    finally:
        if directory is not None and state is not None:
            cleanup(directory, state, children)
            print("owned_cross_service_resources_cleaned", flush=True)


if __name__ == "__main__":
    try:
        run()
    except Exception:
        print("DENIED: cross_service_validation_failed; inspect sanitized local evidence", file=sys.stderr)
        raise SystemExit(1)
