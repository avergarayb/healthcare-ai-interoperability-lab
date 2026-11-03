"""Explicit TASK 004 live revocation. Own IAM/AI only; one real JWT, never persisted."""
from __future__ import annotations

import json
import os
import socket
import sqlite3
import subprocess
import sys
import time
from contextlib import closing

import lab
from oidc_harness import Http, Trust
from verify_python_resource_server import SERVICE, check, startup, stop_process

PORT = 18394
PRINCIPAL = "fixture-ai-workload"
PERMISSION = "iam.workload-context.read"


def operate(directory, operation, *arguments):
    environment = {k: v for k, v in os.environ.items() if k.upper() in {
        "PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "USERPROFILE", "COMSPEC", "PATHEXT"}}
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run([str(SERVICE / ".venv/Scripts/python.exe"), "-B", "-m", "app.trusted_identity_registry_cli",
                             operation, "--db", str(directory / "identity-registry.sqlite"), *arguments],
                            cwd=SERVICE, env=environment, capture_output=True, text=True, timeout=15)
    if result.returncode != 0:
        raise lab.Denied("registry_CLI_failed")
    return json.loads(result.stdout)


def run():
    directory = state = process = log = None
    results, remaining = [], []
    stage = "preparation"
    try:
        lab.free_port(PORT)
        directory, state = lab.prepare(18090, 18190)
        print("run_id=" + state["run_id"], flush=True)
        lab.start(directory, state)
        http = Http(state["origin"])
        trust = Trust.load(http)
        config = lab.read(SERVICE / "oidc-workload.example.json")
        config.update(provider_id="keycloak-lab", enabled=True, allow_http_loopback=True, issuer=trust.issuer,
                      discovery_url=trust.issuer + "/.well-known/openid-configuration",
                      expected_jwks_uri=trust.issuer + "/protocol/openid-connect/certs",
                      allowed_organization_ids=["org-lab-a", "org-lab-b"], bindings=[],
                      endpoint_allowlist=[trust.issuer + suffix for suffix in (
                          "/.well-known/openid-configuration", "/protocol/openid-connect/certs",
                          "/protocol/openid-connect/token", "/protocol/openid-connect/auth")])
        fixture = lab.read(SERVICE / "trusted-identity-registry.example.json")
        fixture.update(provider_id="keycloak-lab", issuer=trust.issuer)
        fixture["bindings"][0]["issuer"] = trust.issuer
        trust_file, fixture_file = directory / "python-trust.json", directory / "registry-fixture.json"
        lab.save(trust_file, config)
        lab.save(fixture_file, fixture)
        stage = "registry_initialization"
        operate(directory, "init", "--fixture", str(fixture_file), "--operator-label", "synthetic-lab-operator")
        stage = "AI_startup"
        process, log, opener = startup(directory, trust_file, "AI-registry", PORT, registry_path=directory / "identity-registry.sqlite")
        # Acquire only after startup. Keep the unchanged fixture's 30-second lifetime.
        secret = lab.read(directory / "secrets.json")["clients"]["lab-ai-workload"]
        encoded = http.request(trust.issuer + "/protocol/openid-connect/token", {
            "grant_type": "client_credentials", "client_id": "lab-ai-workload", "client_secret": secret})["access_token"]
        claims = trust.decode(encoded, "healthcare-ai-api", required=["iss", "sub", "aud", "iat", "exp"])
        original = encoded

        def case(name, status, organization=None):
            nonlocal stage
            stage = name
            if encoded != original:
                raise lab.Denied("token_changed")
            # Revalidate the original real signature/issuer/audience/expiry for each control.
            current = trust.decode(encoded, "healthcare-ai-api", required=["iss", "sub", "aud", "iat", "exp"])
            if any(current[k] != claims[k] for k in ("iss", "sub", "aud", "iat", "exp")):
                raise lab.Denied("token_evidence_changed")
            check(opener, encoded, status, name, results, port=PORT,
                  extra=None if organization is None else {"X-IAM-Lab-Organization": organization})
            lifetime = claims["exp"] - time.time()
            if lifetime <= 0:
                raise lab.Denied("inconclusive_token_expired_during_control")
            remaining.append(lifetime)
            results[-1].update(same_original_token=True, signature_issuer_audience_valid=True,
                               token_valid_after_response=True)

        def mutate(operation, *args):
            return operate(directory, operation, "--target", PRINCIPAL, *args)

        case("active_workload", 200)
        mutate("revoke-permission", "--organization", "org-lab-a", "--permission", PERMISSION)
        case("permission_revoked_same_valid_JWT", 403)
        mutate("grant-permission", "--organization", "org-lab-a", "--permission", PERMISSION)
        case("permission_explicitly_restored", 200)
        mutate("revoke-membership", "--organization", "org-lab-a")
        case("membership_revoked_same_valid_JWT", 403, "org-lab-a")
        mutate("grant-membership", "--organization", "org-lab-a")
        case("membership_explicitly_restored", 200)
        mutate("disable-principal")
        case("principal_disabled_same_valid_JWT", 401)
        mutate("enable-principal")
        case("principal_explicitly_restored", 200)
        case("cross_org_without_membership", 403, "org-lab-b")
        operate(directory, "disable-binding", "--target", "binding-ai")
        case("binding_disabled_same_valid_JWT", 401)
        operate(directory, "enable-binding", "--target", "binding-ai")
        case("binding_explicitly_restored", 200)
        mutate("grant-membership", "--organization", "org-lab-b")
        case("multiple_memberships_require_selection", 403)
        case("cross_org_no_permission_union", 403, "org-lab-b")
        case("explicit_authorized_org", 200, "org-lab-a")
        stage = "persistent_evidence"
        with closing(sqlite3.connect((directory / "identity-registry.sqlite").as_uri() + "?mode=ro", uri=True)) as connection:
            changes = connection.execute("SELECT operation,count(*) FROM registry_policy_change_audit GROUP BY operation ORDER BY operation").fetchall()
            revision = connection.execute("SELECT revision FROM registry_metadata").fetchone()[0]
            unverified = connection.execute("SELECT count(*) FROM registry_policy_change_audit WHERE operator_verified=0").fetchone()[0]
        with closing(sqlite3.connect((directory / "oidc-audit.sqlite").as_uri() + "?mode=ro", uri=True)) as connection:
            access = connection.execute("SELECT outcome,reason_code,count(*) FROM oidc_workload_security_audit_v1 GROUP BY outcome,reason_code").fetchall()
        if (sum(row[2] for row in access) != len(results) or revision != 10 or unverified != revision
                or dict(changes).get("revoke-permission") != 1):
            raise lab.Denied("persistent_evidence_mismatch")
        evidence = {"run_id": state["run_id"], "cases": results, "change_audit_summary": changes,
                    "access_audit_summary": access, "registry_revision": revision,
                    "all_operator_labels_unverified": True, "same_original_JWT_for_all_controls": True,
                    "minimum_token_remaining_seconds_after_response": round(min(remaining), 3),
                    "provider_lifetime_unchanged": True, "java_hapi_calls": "none",
                    "live_storage_failure_injection": "not performed; deterministic coverage only"}
        lab.save(directory / "trusted-registry-evidence.json", evidence)
        print("live_registry_controls_passed=" + str(len(results)), flush=True)
    except Exception as error:
        if directory is not None:
            failure = {"stage": stage, "error_type": type(error).__name__, "completed_cases": results}
            if isinstance(error, lab.Denied):
                failure["reason"] = str(error)
            lab.save(directory / "trusted-registry-failure.json", failure)
        raise
    finally:
        stop_process(process, log)
        if directory is not None and state is not None:
            lab.cleanup(directory, state)
            after = lab.inventory()
            baseline_preserved = all(set(state["baseline"][k]) <= set(after[k]) for k in after)
            owned_removed = all(not (set(state["owned"][k]) & set(after[k])) for k in after)
            with socket.socket() as probe:
                probe.settimeout(0.2)
                listener_closed = probe.connect_ex(("127.0.0.1", PORT)) != 0
            secrets_removed = all(not (directory / name).exists() for name in lab.SECRET_FILES)
            cleanup = {"baseline_preserved": baseline_preserved, "owned_resources_removed": owned_removed,
                       "AI_listener_closed": listener_closed, "ephemeral_secrets_removed": secrets_removed,
                       "no_HAPI_operations": True, "no_Java_operations": True,
                       "owned_counts": {k: len(v) for k, v in state["owned"].items()},
                       "baseline_counts": {k: len(v) for k, v in state["baseline"].items()},
                       "final_counts": {k: len(v) for k, v in after.items()}}
            lab.save(directory / "trusted-registry-cleanup.json", cleanup)
            if not all((baseline_preserved, owned_removed, listener_closed, secrets_removed)):
                raise lab.Denied("cleanup_incomplete")
            print("owned_AI_and_IAM_registry_resources_cleaned", flush=True)


if __name__ == "__main__":
    try:
        run()
    except lab.Denied as error:
        print("DENIED: " + str(error), file=sys.stderr)
        raise SystemExit(1)
    except Exception:
        print("DENIED: trusted_registry_live_check_failed; details sanitized locally", file=sys.stderr)
        raise SystemExit(1)
