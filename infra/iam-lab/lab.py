"""Explicit, test-owned Keycloak lifecycle. No product imports or Docker cleanup by name alone."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlencode

from oidc_harness import (AI, INTEROP, WEB, REALM, Denied, Http, HttpFailure,
                          Trust, authorize, callback_code, callback_host, origin_for,
                          pkce_transaction, require_access_purpose)

ROOT = Path(__file__).resolve().parent
RUNTIME = ROOT / ".runtime"
IMAGE = "quay.io/keycloak/keycloak:26.8.1@sha256:3f3c5f8e03c614774b4bd9173b88391fefa4153bfc010d8012d59ad825377332"
LABEL = "org.healthcare.iam-lab."
WORKSPACE = hashlib.sha256(str(ROOT).casefold().encode()).hexdigest()
SECRET_FILES = ("secrets.json", "bootstrap-password.txt", "healthcare-iam-lab-realm.json", "login-url.txt")


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def create(path, value):
    # Exclusive creation; never changes ACLs of an existing file/directory.
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w", encoding="utf-8", newline="\n") as stream:
        stream.write(value)


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def run_dir(run_id):
    if not re.fullmatch(r"[a-f0-9]{32}", run_id):
        raise Denied("invalid_run_id")
    directory = RUNTIME / run_id
    if directory.resolve().parent != RUNTIME.resolve() or directory.is_symlink():
        raise Denied("unsafe_run_directory")
    return directory


def state_for(run_id):
    directory = run_dir(run_id)
    state = read(directory / "state.json")
    if (state["run_id"] != run_id or state["workspace"] != WORKSPACE
            or state["project"] != "iam-lab-" + run_id or state["image"] != IMAGE
            or state["origin"] != origin_for(state["port"])):
        raise Denied("run_identity_mismatch")
    return directory, state


def docker(*args, json_output=False):
    environment = {k: v for k, v in os.environ.items()
                   if not k.upper().startswith(("IAM_LAB_", "COMPOSE_"))}
    result = subprocess.run(["docker", *args], env=environment, capture_output=True,
                            text=True, encoding="utf-8", errors="replace")
    if result.returncode:
        # Docker errors may echo a command, file contents or credentials. Never print them.
        raise Denied("docker_command_failed_" + args[0])
    return json.loads(result.stdout) if json_output else result.stdout.strip()


def local_engine():
    context = docker("context", "inspect", json_output=True)[0]
    endpoint = context["Endpoints"]["docker"]["Host"]
    if os.environ.get("DOCKER_HOST") or not endpoint.startswith(("npipe://", "unix://")):
        raise Denied("local_docker_context_required")
    info = docker("info", "--format", "{{json .}}", json_output=True)
    if info["OSType"] != "linux" or info["Architecture"] not in {"x86_64", "aarch64", "amd64", "arm64"}:
        raise Denied("unsupported_engine")
    if info["MemTotal"] < 2 * 1024**3:
        raise Denied("insufficient_engine_memory")


def inventory():
    return {"container": docker("ps", "-aq", "--no-trunc").split(),
            "volume": docker("volume", "ls", "-q").split(),
            "network": docker("network", "ls", "-q", "--no-trunc").split()}


def free_port(port):
    origin_for(port)
    with socket.socket() as listener:
        if os.name == "nt":
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        listener.bind(("127.0.0.1", port))


def prepare(port, callback_port):
    origin = origin_for(port)
    free_port(port)
    free_port(callback_port)
    if port == callback_port:
        raise Denied("ports_must_differ")
    local_engine()
    baseline = inventory()
    run_id = secrets.token_hex(16)
    directory = run_dir(run_id)
    directory.mkdir(parents=True, exist_ok=False)
    project = "iam-lab-" + run_id
    state = {"run_id": run_id, "workspace": WORKSPACE, "project": project,
             "image": IMAGE, "port": port, "origin": origin,
             "callback": f"http://127.0.0.1:{callback_port}/callback",
             "baseline": baseline, "owned": {"container": [], "volume": [], "network": []},
             "phase": "prepared"}
    save(directory / "state.json", state)
    realm = read(ROOT / "realm.json")
    credentials = {"bootstrap": secrets.token_urlsafe(40), "clients": {}, "humans": {}}
    for client in realm["clients"]:
        if client.get("serviceAccountsEnabled"):
            value = secrets.token_urlsafe(40)
            credentials["clients"][client["clientId"]] = value
            client["secret"] = value
        if client["clientId"] == WEB:
            client["redirectUris"] = [state["callback"]]
    for user in realm["users"]:
        if not user.get("serviceAccountClientId"):
            value = secrets.token_urlsafe(40)
            credentials["humans"][user["username"]] = value
            user["credentials"] = [{"type": "password", "value": value, "temporary": False}]
    create(directory / "secrets.json", json.dumps(credentials, indent=2))
    create(directory / "bootstrap-password.txt", credentials["bootstrap"])
    create(directory / "healthcare-iam-lab-realm.json", json.dumps(realm))
    values = {"IAM_LAB_PROJECT": project, "IAM_LAB_RUN_ID": run_id,
              "IAM_LAB_WORKSPACE": WORKSPACE, "IAM_LAB_ORIGIN": origin,
              "IAM_LAB_HTTP_PORT": port, "IAM_LAB_RUN_DIR": directory.as_posix()}
    # Quotes protect a workspace containing spaces; values contain no credentials.
    create(directory / "compose.env", "".join(f'{key}="{value}"\n' for key, value in values.items()))
    return directory, state


def compose(directory, state, *args):
    return docker("compose", "--env-file", str(directory / "compose.env"),
                  "-f", str(ROOT / "compose.yaml"), "-p", state["project"], "--profile", "iam-lab", *args)


def owned_labels(state, labels):
    expected = {LABEL + "owner": "iam-lab-v1", LABEL + "run": state["run_id"],
                LABEL + "workspace": WORKSPACE, "com.docker.compose.project": state["project"]}
    if any((labels or {}).get(k) != v for k, v in expected.items()):
        raise Denied("resource_ownership_mismatch")


def inspect_owned(state, kind, identity):
    if identity in state["baseline"][kind]:
        raise Denied("preexisting_resource_protected")
    args = ("inspect", identity) if kind == "container" else (kind, "inspect", identity)
    item = docker(*args, json_output=True)[0]
    actual = item["Name"] if kind == "volume" else item["Id"]
    if actual != identity:
        raise Denied("resource_identity_mismatch")
    owned_labels(state, item.get("Labels") if kind != "container" else item["Config"].get("Labels"))
    return item


def record_owned(directory, state):
    # Used even after a partial up failure; select labels first, verify full identity next.
    for kind in ("container", "volume", "network"):
        command = ("ps", "-aq", "--no-trunc") if kind == "container" else (kind, "ls", "-q")
        if kind == "network":
            command += ("--no-trunc",)
        ids = docker(*command, "--filter", "label=" + LABEL + "run=" + state["run_id"],
                     "--filter", "label=com.docker.compose.project=" + state["project"]).split()
        for identity in ids:
            inspect_owned(state, kind, identity)
            if identity not in state["owned"][kind]:
                state["owned"][kind].append(identity)
    save(directory / "state.json", state)


def running_container(state):
    if len(state["owned"]["container"]) != 1:
        raise Denied("unexpected_container_count")
    item = inspect_owned(state, "container", state["owned"]["container"][0])
    expected = {"8080/tcp": [{"HostIp": "127.0.0.1", "HostPort": str(state["port"])}]}
    if not item["State"]["Running"] or item["Config"]["Image"] != IMAGE:
        raise Denied("owned_fixture_not_running")
    if item["HostConfig"]["PortBindings"] != expected:
        raise Denied("unsafe_port_binding")
    if item["NetworkSettings"]["Ports"] != expected:
        raise Denied("host_port_not_published")
    return item


def start(directory, state):
    if state["phase"] != "prepared":
        raise Denied("fresh_run_required_no_reimport")
    local_engine()
    free_port(state["port"])
    # Never adopt a previous project, including a partially failed run.
    for kind in ("container", "volume", "network"):
        command = ("ps", "-aq") if kind == "container" else (kind, "ls", "-q")
        if docker(*command, "--filter", "label=com.docker.compose.project=" + state["project"]):
            raise Denied("project_already_exists")
    compose(directory, state, "config", "--quiet")
    docker("pull", IMAGE)
    image = docker("image", "inspect", IMAGE, json_output=True)[0]
    if IMAGE.split("@", 1)[1] not in [v.split("@", 1)[-1] for v in image.get("RepoDigests", [])]:
        raise Denied("image_digest_mismatch")
    state["phase"] = "starting"
    save(directory / "state.json", state)
    try:
        compose(directory, state, "up", "-d", "--no-recreate", "--pull", "never", "keycloak")
    finally:
        record_owned(directory, state)
    running_container(state)
    http = Http(state["origin"])
    deadline = time.monotonic() + 150
    while time.monotonic() < deadline:
        try:
            Trust.load(http)
            state["phase"] = "running"
            save(directory / "state.json", state)
            return
        except HttpFailure:
            time.sleep(1)
    raise Denied("keycloak_startup_timeout")


def cleanup(directory, state):
    local_engine()
    # Discover only this run if startup failed between creation and recording.
    record_owned(directory, state)
    live = inventory()
    for kind in ("container", "volume", "network"):
        for identity in state["owned"][kind]:
            if identity not in live[kind]:
                continue
            item = inspect_owned(state, kind, identity)
            if kind == "container":
                docker("stop", "--time", "15", identity)
                docker("rm", identity)
            elif kind == "volume":
                # Refuse if any remaining container uses the volume; never force removal.
                if docker("ps", "-aq", "--filter", "volume=" + identity):
                    raise Denied("volume_still_in_use")
                docker("volume", "rm", identity)
            else:
                if item.get("Containers"):
                    raise Denied("network_still_in_use")
                docker("network", "rm", identity)
    for name in SECRET_FILES:
        path = directory / name
        if path.is_symlink() or path.resolve().parent != directory.resolve():
            raise Denied("unsafe_secret_cleanup_path")
        path.unlink(missing_ok=True)
    state["phase"] = "cleaned"
    save(directory / "state.json", state)


def verify(directory, state):
    if state["phase"] != "running":
        raise Denied("running_fixture_required")
    running_container(state)
    http = Http(state["origin"])
    trust = Trust.load(http)
    credentials = read(directory / "secrets.json")["clients"]
    policy = read(ROOT / "policy.json")
    endpoint = trust.issuer + "/protocol/openid-connect/token"
    cases = []

    def expect(name, category, operation, reason=None):
        try:
            operation()
            if reason is not None:
                raise Denied("negative_case_accepted_" + name)
        except Denied as error:
            if reason is None or str(error) != reason:
                raise
        cases.append({"case": name, "category": category, "result": "PASS", "expected": reason or "accepted"})

    tokens = {}
    for client, secret in credentials.items():
        response = http.request(endpoint, {"grant_type": "client_credentials", "client_id": client, "client_secret": secret})
        if response.get("token_type", "").lower() != "bearer" or "id_token" in response:
            raise Denied("unexpected_client_credentials_response")
        tokens[client] = response["access_token"]
    ai, interop = tokens["lab-ai-workload"], tokens["lab-python-to-java"]
    expect("ai_profile", "A", lambda: trust.access(ai, AI, policy))
    expect("interop_profile", "A", lambda: trust.access(interop, INTEROP, policy))
    expect("ai_against_java", "A", lambda: trust.access(ai, INTEROP, policy), "audience_mismatch")
    expect("java_against_ai", "A", lambda: trust.access(interop, AI, policy), "audience_mismatch")
    expect("unknown_workload", "A", lambda: trust.access(tokens["lab-unregistered-workload"], AI, policy), "workload_unknown")
    wrong = Trust(trust.issuer + "-wrong", trust.keys)
    expect("wrong_expected_issuer", "A", lambda: wrong.access(ai, AI, policy), "issuer_mismatch")
    expect("organization_denied", "A+policy", lambda: authorize(trust.access(ai, AI, policy), "org-lab-b", []), "organization_not_authorized")
    for client, scope in (("lab-ai-workload", "iam-interop"), ("lab-python-to-java", "iam-ai")):
        try:
            http.request(endpoint, {"grant_type": "client_credentials", "client_id": client,
                                    "client_secret": credentials[client], "scope": scope})
        except HttpFailure as error:
            if error.status != 400 or error.code != "invalid_scope":
                raise Denied("unexpected_scope_error") from None
        else:
            raise Denied("unassigned_scope_accepted")
        cases.append({"case": client + "_forbidden_scope", "category": "A", "result": "PASS", "expected": "invalid_scope"})
    # Mutations are B: never described as unchanged provider-issued tokens.
    parts = ai.split(".")
    signature = ("A" if parts[2][0] != "A" else "B") + parts[2][1:]
    expect("tampered_signature", "B", lambda: trust.access(".".join(parts[:2] + [signature]), AI, policy), "token_invalid")
    import jwt
    for name, value, reason in (("alg", "HS256", "algorithm_not_allowed"), ("kid", "unknown-fixture-key", "unknown_key_id")):
        header = jwt.get_unverified_header(ai)
        header[name] = value
        encoded = jwt.utils.base64url_encode(json.dumps(header).encode()).decode()
        expect("modified_" + name, "B", lambda e=encoded: trust.access(".".join([e, *parts[1:]]), AI, policy), reason)
    both = policy["humans"]["00000000-0000-4000-8000-000000000103"]
    expect("ambiguous_membership", "C", lambda: authorize(both, None, []), "organization_selection_required")
    expect("permission_union_denied", "C", lambda: authorize(both, "org-lab-a", ["fixture.interop.read"]), "permission_not_granted")
    # Wait for actual Keycloak expiry; no modified clock, claims or synthetic signing key.
    claims = trust.decode(ai, AI, required=["iss", "sub", "aud", "exp", "iat"])
    delay = max(0, claims["exp"] - time.time() + 1)
    if delay > 35:
        raise Denied("unexpected_fixture_token_lifetime")
    time.sleep(delay)
    expect("actual_token_expired", "A", lambda: trust.access(ai, AI, policy), "token_expired")
    report = {"run_id": state["run_id"], "image": IMAGE, "issuer": trust.issuer,
              "jwks_uri": trust.issuer + "/protocol/openid-connect/certs", "cases": cases,
              "client_credentials": "three distinct actual service-account tokens, memory only",
              "interactive_pkce": "PENDING manual browser interaction",
              "actual_id_token_as_api": "PENDING interactive PKCE; synthetic vector tested separately"}
    save(directory / "evidence.json", report)
    return report


def id_token_api_rejections(trust, token, policy):
    """Use the original ID token. Never relax an API audience or modify signed claims."""
    # Human crypto/nonce validation occurs in login before this diagnostic. Verify
    # crypto again under its actual WEB audience for the independent purpose gate.
    claims = trust.decode(token, WEB, required=["iss", "sub", "aud", "exp", "iat", "typ"])
    try:
        require_access_purpose(claims)
    except Denied as error:
        if str(error) != "access_token_required":
            raise
    else:
        raise Denied("id_token_purpose_gate_accepted")
    results = {}
    for audience in (AI, INTEROP):
        try:
            trust.access(token, audience, policy)
        except Denied as error:
            if str(error) != "audience_mismatch":
                raise Denied("unexpected_id_token_profile_rejection") from None
        else:
            raise Denied("id_token_accepted_as_api")
        # Explicit audience-only check, without relying on missing workload claims.
        try:
            trust.decode(token, audience, required=["iss", "sub", "aud", "exp", "iat"])
        except Denied as error:
            if str(error) != "audience_mismatch":
                raise
        else:
            raise Denied("unexpected_id_token_api_audience")
        results[audience] = {"result": "DENIED", "profile_reason": "audience_mismatch",
                             "audience_check": "DENIED: audience_mismatch",
                             "independent_purpose_check": "DENIED: access_token_required"}
    return results


def login(directory, state, organization):
    if state["phase"] != "running":
        raise Denied("running_fixture_required")
    running_container(state)
    from urllib.parse import urlsplit
    port = urlsplit(state["callback"]).port
    if state["callback"] != f"http://127.0.0.1:{port}/callback":
        raise Denied("invalid_callback_uri")
    free_port(port)
    http = Http(state["origin"])
    trust = Trust.load(http)
    transaction = pkce_transaction(trust.issuer, state["callback"])
    result = {"run_id": state["run_id"], "status": "PENDING", "stage": "awaiting_browser"}

    class Callback(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(2)

        def log_message(self, *args):
            pass

        def do_GET(self):
            try:
                result["stage"] = "callback_transaction"
                callback_host(self.headers, port)
                code = callback_code(self.path, transaction)
                result["stage"] = "authorization_code_exchange"
                response = http.request(trust.issuer + "/protocol/openid-connect/token", {
                    "grant_type": "authorization_code", "client_id": WEB, "code": code,
                    "redirect_uri": transaction["redirect"], "code_verifier": transaction["verifier"]})
                policy = read(ROOT / "policy.json")
                result["stage"] = "id_token_verification"
                binding = trust.identity(response["id_token"], transaction["nonce"], policy)
                result["stage"] = "membership"
                result.update(authorize(binding, organization, []))
                result["stage"] = "id_token_api_rejections"
                result["api_profiles"] = id_token_api_rejections(trust, response["id_token"], policy)
                result.update(code_pkce="PASS", id_token_signature_issuer_web_audience_nonce_expiry="PASS",
                              exact_callback_host_uri_state="PASS", transaction_consumed=transaction["used"],
                              tokens_persisted=False, human_review_session_created=False)
                result["stage"] = "completed"
                result["status"] = "PASS"
            except (Denied, HttpFailure) as error:
                stage = result["stage"]
                result.clear()
                result.update(run_id=state["run_id"], status="DENIED", stage=stage, reason=str(error))
            except KeyError:
                result.clear()
                result.update(run_id=state["run_id"], status="DENIED", reason="required_response_field_missing")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write(b"IAM laboratory callback processed. Consult the local sanitized evidence file.")

    server = HTTPServer(("127.0.0.1", port), Callback)
    server.timeout = 1
    url = trust.issuer + "/protocol/openid-connect/auth?" + urlencode({
        "response_type": "code", "client_id": WEB, "redirect_uri": state["callback"],
        "scope": "openid", "state": transaction["state"], "nonce": transaction["nonce"],
        "code_challenge": transaction["challenge"], "code_challenge_method": "S256"})
    path = directory / "login-url.txt"
    create(path, url)
    print("Open the ignored login-url.txt locally; synthetic passwords are in this run's ignored secrets.json. Timeout: 300s.", flush=True)
    try:
        while result["status"] == "PENDING" and time.monotonic() < transaction["deadline"]:
            server.handle_request()
    finally:
        server.server_close()
        path.unlink(missing_ok=True)
    if result["status"] == "PENDING":
        result.update(status="INCOMPLETE", reason="browser_callback_timeout")
    save(directory / "pkce-evidence.json", result)
    if result["status"] != "PASS":
        raise Denied("interactive_login_incomplete_or_denied")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["run", "start", "verify", "login", "stop"])
    parser.add_argument("--run-id")
    parser.add_argument("--port", type=int, default=18090)
    parser.add_argument("--callback-port", type=int, default=18190)
    parser.add_argument("--organization")
    args = parser.parse_args()
    directory = state = None
    try:
        if args.command in {"run", "start"}:
            if args.run_id:
                raise Denied("new_run_required")
            directory, state = prepare(args.port, args.callback_port)
            print("run_id=" + state["run_id"], flush=True)
            start(directory, state)
            if args.command == "run":
                report = verify(directory, state)
                print("verification_cases_passed=" + str(len(report["cases"])), flush=True)
        else:
            if not args.run_id:
                raise Denied("run_id_required")
            directory, state = state_for(args.run_id)
            if args.command == "stop":
                cleanup(directory, state)
            elif args.command == "verify":
                verify(directory, state)
            else:
                login(directory, state, args.organization)
    except (Denied, HttpFailure) as error:
        print("DENIED: " + str(error), file=sys.stderr)
        return 1
    except Exception:
        print("DENIED: unexpected_local_failure (details suppressed to protect secrets)", file=sys.stderr)
        return 1
    finally:
        if (directory is not None and state is not None
                and (args.command == "run" or (args.command == "start" and state["phase"] != "running"))):
            cleanup(directory, state)
            print("owned_resources_cleaned; evidence=" + str(directory / "evidence.json"), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
