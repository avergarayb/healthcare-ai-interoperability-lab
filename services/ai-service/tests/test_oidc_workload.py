"""Deterministic resource-server conformance; no IdP, Java, HAPI or Docker."""
import json
import sqlite3
import time

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings
from app.oidc_config import AUDIENCE, PERMISSION, ROUTE, Rejected, TrustConfig, load_config
from app.oidc_verifier import AccessVerifier, KeyCache, MetadataClient
from app.oidc_workload import WorkloadBoundary, configure_boundary
from app.oidc_workload_audit import WorkloadAudit

ISSUER = "https://identity.example.invalid/realms/lab"
SUBJECT = "00000000-0000-4000-8000-000000000201"


def registration():
    return dict(contract_version="python-oidc-workload-v1", provider_id="synthetic-provider", enabled=True,
                issuer=ISSUER, discovery_url=ISSUER + "/.well-known/openid-configuration",
                expected_jwks_uri=ISSUER + "/protocol/openid-connect/certs",
                endpoint_allowlist=[ISSUER + suffix for suffix in (
                    "/.well-known/openid-configuration", "/protocol/openid-connect/certs",
                    "/protocol/openid-connect/auth", "/protocol/openid-connect/token")],
                accepted_audiences=[AUDIENCE], allowed_algorithms=["RS256"],
                access_token_profile="keycloak-client-credentials-v1", allow_http_loopback=False,
                allowed_organization_ids=["org-lab-a"], clock_skew_seconds=0,
                max_access_token_lifetime_seconds=300, jwks_refresh_seconds=300, jwks_hard_ttl_seconds=900,
                unknown_kid_refresh_min_interval_seconds=30, http_timeout_seconds=2.0, metadata_max_bytes=1048576,
                bindings=[dict(client_id="lab-ai-workload", external_subject=SUBJECT,
                               internal_principal_id="fixture-ai-workload", principal_type="workload",
                               binding_enabled=True, principal_enabled=True, organization_id="org-lab-a",
                               membership_enabled=True, audience=AUDIENCE, permissions=[PERMISSION])])


def config(value=None):
    return TrustConfig.model_validate_json(json.dumps(registration() if value is None else value))


@pytest.fixture(scope="module")
def key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def public(key, kid="known"):
    value = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    value.update(kid=kid, alg="RS256", use="sig")
    return value


def token(key, **changes):
    now = int(time.time())
    claims = dict(iss=ISSUER, sub=SUBJECT, aud=AUDIENCE, iat=now, exp=now + 180,
                  jti="synthetic-event", azp="lab-ai-workload", typ="Bearer")
    claims.update(changes)
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "known"})


def fetcher(key):
    def fetch(url):
        if url.endswith("openid-configuration"):
            return {"issuer": ISSUER, "jwks_uri": ISSUER + "/protocol/openid-connect/certs",
                    "token_endpoint": ISSUER + "/protocol/openid-connect/token",
                    "authorization_endpoint": ISSUER + "/protocol/openid-connect/auth"}
        return {"keys": [public(key)]}
    return fetch


@pytest.fixture
def boundary(tmp_path, key):
    path = tmp_path / "trust.json"
    path.write_text(json.dumps(registration()), encoding="utf-8")
    value = WorkloadBoundary(str(path), str(tmp_path / "audit.sqlite"))
    value.verifier = AccessVerifier(value.config, KeyCache(value.config, fetcher(key)))
    app = FastAPI()
    from fastapi import Request
    @app.get(ROUTE)
    def route(request: Request):
        return value.handle(request)
    with TestClient(app) as client:
        yield value, client, tmp_path / "audit.sqlite"


def rows(path):
    connection = sqlite3.connect(path)
    try:
        connection.row_factory = sqlite3.Row
        return [dict(row) for row in connection.execute("SELECT * FROM oidc_workload_security_audit_v1")]
    finally:
        connection.close()


def test_known_workload_minimized_context_and_durable_audit(boundary, key):
    _, client, path = boundary
    response = client.get(ROUTE, headers={"Authorization": "Bearer " + token(key)})
    assert response.status_code == 200
    data = response.json()
    assert data["internal_principal_id"] == "fixture-ai-workload"
    assert data["principal_type"] == "workload" and data["authentication_method"] == "oauth2_client_credentials"
    assert data["organization_id"] == "org-lab-a" and data["effective_permissions"] == [PERMISSION]
    assert all(name not in data for name in ("external_subject", "external_issuer", "provider_id", "token"))
    event = rows(path)[0]
    assert event["outcome"] == "allowed" and event["actor_type"] == "workload"
    assert event["actor_id"] == "fixture-ai-workload"
    assert SUBJECT not in json.dumps(event)


@pytest.mark.parametrize("claims,reason", [
    ({"iss": ISSUER + "-wrong"}, "provider_untrusted"),
    ({"aud": "healthcare-interop-api"}, "audience_rejected"),
    ({"aud": [AUDIENCE, "healthcare-interop-api"]}, "audience_rejected"),
    ({"aud": [AUDIENCE, AUDIENCE]}, "audience_rejected"),
    ({"typ": "ID"}, "purpose_rejected"),
    ({"exp": int(time.time()) - 1}, "token_expired"),
    ({"nbf": int(time.time()) + 60}, "time_rejected"),
    ({"iat": int(time.time()) + 60}, "time_rejected"),
    ({"exp": int(time.time()) + 600}, "time_rejected"),
    ({"azp": "unknown"}, "binding_unknown"),
    ({"sub": "human-subject"}, "binding_unknown"),
    ({"jti": None}, "verification_rejected"),
])
def test_rejected_tokens_are_audited_without_identity_or_claims(boundary, key, claims, reason):
    _, client, path = boundary
    response = client.get(ROUTE, headers={"Authorization": "Bearer " + token(key, **claims)})
    assert response.status_code == 401
    assert response.json() == {"error": "unauthorized"}
    event = rows(path)[0]
    assert event["reason_code"] == reason and event["outcome"] == "denied"
    assert event["actor_id"] is None and event["organization_id"] is None


@pytest.mark.parametrize("headers,reason", [
    ([], "credential_missing"),
    ([("Authorization", "Bearer a.b.c"), ("Authorization", "Bearer a.b.c")], "credential_ambiguous"),
    ([("Authorization", "bearer a.b.c")], "credential_malformed"),
    ([("Authorization", "Bearer  a.b.c")], "credential_malformed"),
    ([("Authorization", "Bearer a.b.c, Bearer a.b.c")], "credential_malformed"),
    ([("Authorization", "Bearer " + "a" * 17000)], "credential_malformed"),
    ([("X-Service-Token", "synthetic")], "credential_conflict"),
    ([("Authorization", "Bearer a.b.c"), ("Cookie", "human=synthetic")], "credential_conflict"),
    ([("Authorization", "Bearer a.b.c"), ("X-Service-Token", "synthetic")], "credential_conflict"),
])
def test_credentials_deny_before_provider_io(boundary, monkeypatch, headers, reason):
    value, client, path = boundary
    monkeypatch.setattr(value.verifier, "verify", lambda *_: pytest.fail("No provider I/O permitted"))
    assert client.get(ROUTE, headers=headers).status_code == 401
    assert rows(path)[0]["reason_code"] == reason


@pytest.mark.parametrize("field,value,reason", [
    ("binding_enabled", False, "binding_disabled"), ("principal_enabled", False, "principal_disabled"),
    ("membership_enabled", False, "organization_rejected"),
    ("organization_id", "org-not-allowed", "organization_rejected"),
    ("permissions", [], "policy_rejected"),
])
def test_trusted_policy_denials(boundary, key, field, value, reason):
    boundary_value, client, path = boundary
    data = registration()
    data["bindings"][0][field] = value
    boundary_value.config = config(data)
    response = client.get(ROUTE, headers={"Authorization": "Bearer " + token(key)})
    assert response.status_code == 403 and rows(path)[0]["reason_code"] == reason


def test_claims_cannot_grant_permissions_or_select_organization(boundary, key):
    _, client, _ = boundary
    response = client.get(ROUTE, headers={"Authorization": "Bearer " + token(key, groups=["admin"],
        roles=["iam.admin"], organization="org-lab-b", tenant="unregistered", scope="*"), "X-Organization-ID": "org-lab-b"})
    assert response.status_code == 200
    assert response.json()["organization_id"] == "org-lab-a"
    assert response.json()["effective_permissions"] == [PERMISSION]


@pytest.mark.parametrize("failure", ["signature", "algorithm", "kid", "jku", "missing"])
def test_signature_header_and_missing_claims(boundary, key, failure):
    _, client, _ = boundary
    if failure == "signature":
        encoded = token(rsa.generate_private_key(public_exponent=65537, key_size=2048))
    elif failure == "algorithm":
        encoded = jwt.encode({"sub": SUBJECT}, "synthetic-test-only-secret-of-sufficient-length", algorithm="HS256")
    elif failure == "missing":
        encoded = jwt.encode({"iss": ISSUER}, key, algorithm="RS256", headers={"kid": "known"})
    else:
        original = jwt.decode(token(key), options={"verify_signature": False})
        header = {"kid": "missing"} if failure == "kid" else {"kid": "known", "jku": "http://169.254.169.254/"}
        encoded = jwt.encode(original, key, algorithm="RS256", headers=header)
    assert client.get(ROUTE, headers={"Authorization": "Bearer " + encoded}).status_code == 401


def test_audit_failure_discloses_no_context(boundary, key, monkeypatch):
    value, client, _ = boundary
    def failed(**kwargs):
        raise Rejected("audit_unavailable", 503)
    monkeypatch.setattr(value.audit, "append", failed)
    for headers in ({"Authorization": "Bearer " + token(key)}, {}):
        response = client.get(ROUTE, headers=headers)
        assert response.status_code == 503 and response.json() == {"error": "unavailable"}


def test_configuration_incomplete_and_provider_disabled(boundary, key):
    value, client, path = boundary
    value.config = None
    assert client.get(ROUTE, headers={"Authorization": "Bearer " + token(key)}).status_code == 503
    assert rows(path)[0]["reason_code"] == "configuration_incomplete"
    value.config = config()
    value.verifier = AccessVerifier(value.config.model_copy(update={"enabled": False}))
    assert client.get(ROUTE, headers={"Authorization": "Bearer " + token(key)}).status_code == 503


def test_disabled_default_has_no_route_or_openapi_or_io(monkeypatch, tmp_path):
    monkeypatch.setenv("OIDC_WORKLOAD_LAB_ENABLED", "false")
    monkeypatch.setenv("OIDC_WORKLOAD_TRUST_CONFIG_PATH", str(tmp_path / "missing"))
    monkeypatch.setattr("app.oidc_workload.load_config", lambda *_: pytest.fail("disabled must not load trust"))
    settings = Settings.from_env()
    assert not settings.oidc_workload_lab_enabled
    app = FastAPI()
    configure_boundary(app, settings)
    with TestClient(app) as client:
        assert client.get(ROUTE).status_code == 404
        assert ROUTE not in client.get("/openapi.json").json()["paths"]


def test_legacy_store_path_cannot_be_reused(tmp_path):
    path = tmp_path / "legacy.sqlite"
    value = WorkloadBoundary("", str(path), (str(path),))
    assert value.audit is None and not path.exists()


def test_foreign_audit_schema_remains_unchanged(tmp_path):
    path = tmp_path / "legacy.sqlite"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE security_audit_events (id TEXT)")
    before = path.read_bytes()
    with pytest.raises(Rejected):
        WorkloadAudit(str(path)).append(reason="credential_missing", correlation="00000000-0000-4000-8000-000000000001")
    assert path.read_bytes() == before


@pytest.mark.parametrize("field,value", [("issuer", "http://untrusted.invalid"), ("issuer", "http://169.254.169.254"),
    ("allowed_algorithms", ["HS256"]), ("clock_skew_seconds", 61), ("jwks_hard_ttl_seconds", 901),
    ("unknown_kid_refresh_min_interval_seconds", 1), ("access_token_profile", "any-jwt"),
    ("accepted_audiences", ["healthcare-interop-api"]), ("enabled", "true")])
def test_configuration_rejects_unsafe_or_ambiguous_trust(tmp_path, field, value):
    raw = registration()
    raw[field] = value
    path = tmp_path / "trust.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(Rejected, match="configuration_incomplete"):
        load_config(str(path))


def test_key_cache_rotation_unknown_kid_throttle_and_hard_expiry(key):
    now, calls, unavailable, active_kid = [0], [], [False], ["known"]
    base = fetcher(key)
    def fetch(url):
        calls.append(url)
        if unavailable[0]:
            raise Rejected("provider_unavailable", 503)
        return base(url) if url.endswith("openid-configuration") else {"keys": [public(key, active_kid[0])]}
    cache = KeyCache(config(), fetch, lambda: now[0])
    assert cache.key("known")
    for kid in ("bad-one", "bad-two", "bad-three"):
        with pytest.raises(Rejected, match="unknown_key"):
            cache.key(kid)
    assert len(calls) == 2
    now[0] = 31
    with pytest.raises(Rejected):
        cache.key("bad-four")
    assert len(calls) == 4
    now[0], active_kid[0] = 62, "rotated"
    assert cache.key("rotated")
    with pytest.raises(Rejected, match="unknown_key"):
        cache.key("known")
    now[0], unavailable[0] = 362, True
    assert cache.key("rotated")  # Network outage before hard TTL preserves known trust.
    now[0] = 963
    with pytest.raises(Rejected) as error:
        cache.key("rotated")
    assert error.value.status == 503


@pytest.mark.parametrize("failure", ["issuer", "jwks", "private", "weak", "duplicate"])
def test_untrusted_discovery_and_keys_do_not_enter_cache(key, failure):
    base = fetcher(key)
    def fetch(url):
        value = base(url)
        if url.endswith("openid-configuration") and failure in ("issuer", "jwks"):
            value["issuer" if failure == "issuer" else "jwks_uri"] = "http://169.254.169.254/"
        elif not url.endswith("openid-configuration"):
            if failure == "private":
                value["keys"][0]["d"] = "synthetic-private-material-rejected"
            elif failure == "weak":
                value["keys"] = [public(rsa.generate_private_key(public_exponent=65537, key_size=1024))]
            elif failure == "duplicate":
                value["keys"] *= 2
        return value
    with pytest.raises(Rejected) as error:
        KeyCache(config(), fetch).key("known")
    assert error.value.status == 503


def test_provider_unavailable_is_fail_closed_and_throttled(boundary, key):
    value, client, path = boundary
    calls = []
    def unavailable(url):
        calls.append(url)
        raise Rejected("provider_unavailable", 503)
    value.verifier = AccessVerifier(value.config, KeyCache(value.config, unavailable))
    for _ in range(2):
        assert client.get(ROUTE, headers={"Authorization": "Bearer " + token(key)}).status_code == 503
    assert len(calls) == 1
    assert {r["outcome"] for r in rows(path)} == {"denied"}


def test_concurrent_unknown_keys_coalesce_to_one_refresh(key):
    from concurrent.futures import ThreadPoolExecutor
    calls, now = [], [0]
    base = fetcher(key)
    def fetch(url):
        calls.append(url)
        return base(url)
    cache = KeyCache(config(), fetch, lambda: now[0])
    cache.key("known")
    now[0] = 31
    def rejected(index):
        with pytest.raises(Rejected, match="unknown_key"):
            cache.key("unregistered-" + str(index))
    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(rejected, range(32)))
    assert len(calls) == 4


@pytest.mark.parametrize("failure", ["redirect", "oversize", "timeout", "compressed", "invalid_json"])
def test_metadata_transport_is_bounded_and_never_follows_redirects(monkeypatch, failure):
    class Stream:
        status_code = 302 if failure == "redirect" else 200
        headers = {"content-encoding": "gzip"} if failure == "compressed" else {}
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def iter_bytes(self):
            if failure == "timeout":
                raise httpx.ReadTimeout("synthetic timeout")
            yield b"x" * 1048577 if failure == "oversize" else b"invalid-json"
    class Client:
        def __init__(self, **kwargs):
            assert kwargs["follow_redirects"] is False and kwargs["trust_env"] is False
            assert kwargs["timeout"] == 2.0 and kwargs.get("verify", True) is True
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def stream(self, method, url, **kwargs):
            assert method == "GET" and url == config().discovery_url
            assert kwargs["headers"]["Accept-Encoding"] == "identity"
            return Stream()
    monkeypatch.setattr("app.oidc_verifier.httpx.Client", Client)
    with pytest.raises(Rejected) as error:
        MetadataClient(config()).get(config().discovery_url)
    assert error.value.status == 503
    with pytest.raises(Rejected, match="discovery_mismatch"):
        MetadataClient(config()).get("http://169.254.169.254/unapproved")


def test_duplicate_claim_is_rejected_before_network(boundary, monkeypatch):
    value, client, path = boundary
    monkeypatch.setattr(value.verifier.cache, "key", lambda *_: pytest.fail("no network"))
    header = jwt.utils.base64url_encode(b'{"alg":"RS256","typ":"JWT","kid":"known"}').decode()
    payload = jwt.utils.base64url_encode(b'{"sub":"one","sub":"two"}').decode()
    assert client.get(ROUTE, headers={"Authorization": "Bearer " + header + "." + payload + ".AA"}).status_code == 401
    assert rows(path)[0]["reason_code"] == "verification_rejected"


def test_real_locked_sqlite_fails_closed_without_context(boundary, key):
    _, client, path = boundary
    assert client.get(ROUTE, headers={"Authorization": "Bearer " + token(key)}).status_code == 200
    connection = sqlite3.connect(path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        assert client.get(ROUTE, headers={"Authorization": "Bearer " + token(key)}).status_code == 503
    finally:
        connection.rollback()
        connection.close()
    assert len(rows(path)) == 1


def test_no_expired_context_returned_after_slow_audit(boundary, key, monkeypatch):
    value, client, _ = boundary
    original = value.audit.append
    def slow(**kwargs):
        original(**kwargs)
        monkeypatch.setattr("app.oidc_workload.time", lambda: time.time() + 1000)
    monkeypatch.setattr(value.audit, "append", slow)
    assert client.get(ROUTE, headers={"Authorization": "Bearer " + token(key)}).status_code == 401


def test_default_example_configuration_is_valid_and_disabled():
    from pathlib import Path
    example = Path(__file__).resolve().parents[1] / "oidc-workload.example.json"
    assert load_config(str(example)).enabled is False


def test_real_application_lifespan_keeps_legacy_boundary_independent(tmp_path, key, monkeypatch):
    from dataclasses import replace
    from app import main
    trust = tmp_path / "trust.json"
    trust.write_text(json.dumps(registration()), encoding="utf-8")
    settings = Settings(model_boundary_base_url="http://127.0.0.1:9", model_boundary_path="/api/model-boundary/v1",
                        model_boundary_timeout_seconds=1, model_boundary_service_token="synthetic-legacy-credential",
                        host="127.0.0.1", port=8090, ai_review_db_path=str(tmp_path / "review.sqlite"),
                        human_session_db_path=str(tmp_path / "session.sqlite"),
                        institutional_knowledge_db_path=str(tmp_path / "knowledge.sqlite"),
                        security_audit_db_path=str(tmp_path / "legacy-audit.sqlite"),
                        oidc_workload_lab_enabled=True, oidc_workload_trust_config_path=str(trust),
                        oidc_workload_audit_db_path=str(tmp_path / "oidc-audit.sqlite"))
    original_settings = main.get_settings
    monkeypatch.setattr(main, "get_settings", lambda: settings)
    monkeypatch.setattr("app.oidc_verifier.MetadataClient.get", lambda self, url: fetcher(key)(url))
    monkeypatch.setattr(main, "consume", lambda *_: pytest.fail("denied legacy call must not invoke Java"))
    main.app.dependency_overrides[original_settings] = lambda: settings
    try:
        with TestClient(main.app) as client:
            headers = {"Authorization": "Bearer " + token(key)}
            assert ROUTE in client.get("/openapi.json").json()["paths"]
            assert client.get(ROUTE, headers=headers).status_code == 200
            assert client.get("/internal/agent-context", headers=headers).status_code == 401
            assert client.post("/internal/workflows", headers=headers, json={}).status_code == 401
            assert client.get(ROUTE, headers={"X-Service-Token": settings.model_boundary_service_token}).status_code == 401
    finally:
        main.app.dependency_overrides.clear()
        configure_boundary(main.app, replace(settings, oidc_workload_lab_enabled=False))
    assert not (tmp_path / "session.sqlite").exists()


def test_metadata_network_deadline_excludes_local_tls_client_setup(monkeypatch):
    now = [0]
    monkeypatch.setattr("app.oidc_verifier.time.monotonic", lambda: now[0])
    class Stream:
        status_code, headers = 200, {}
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def iter_bytes(self):
            now[0] += 0.1
            yield b'{"synthetic":"metadata"}'
    class Client:
        def __init__(self, **kwargs): now[0] += 3
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def stream(self, *args, **kwargs): return Stream()
    monkeypatch.setattr("app.oidc_verifier.httpx.Client", Client)
    assert MetadataClient(config()).get(config().discovery_url) == {"synthetic": "metadata"}


def test_loopback_ipv4_binding_preserves_canonical_url_and_tls_controls(monkeypatch):
    value = registration()
    for field in ("issuer", "discovery_url", "expected_jwks_uri"):
        value[field] = value[field].replace("https://identity.example.invalid", "http://localhost:18090")
    value["endpoint_allowlist"] = [u.replace("https://identity.example.invalid", "http://localhost:18090") for u in value["endpoint_allowlist"]]
    value["allow_http_loopback"] = True
    cfg, transports = config(value), []
    def transport(**kwargs):
        transports.append(kwargs)
        return "synthetic-transport"
    class Stream:
        status_code, headers = 200, {}
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def iter_bytes(self): yield b'{}'
    class Client:
        def __init__(self, **kwargs):
            assert kwargs["transport"] == "synthetic-transport" and kwargs["trust_env"] is False
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def stream(self, method, url, **kwargs):
            assert url == cfg.discovery_url and url.startswith("http://localhost:18090/")
            return Stream()
    monkeypatch.setattr("app.oidc_verifier.httpx.HTTPTransport", transport)
    monkeypatch.setattr("app.oidc_verifier.httpx.Client", Client)
    assert MetadataClient(cfg).get(cfg.discovery_url) == {}
    assert transports == [{"local_address": "127.0.0.1", "trust_env": False, "verify": True}]


def test_concurrent_initial_audit_appends_remain_serialized(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    import uuid
    store = WorkloadAudit(str(tmp_path / "concurrent.sqlite"))
    def append(_):
        store.append(reason="credential_missing", correlation=str(uuid.uuid4()))
    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(append, range(16)))
    assert len(rows(tmp_path / "concurrent.sqlite")) == 16


def test_only_oidc_metadata_sdk_logs_are_suppressed(monkeypatch, caplog):
    import logging
    class Stream:
        status_code, headers = 200, {}
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def iter_bytes(self): yield b'{}'
    class Client:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def stream(self, *args, **kwargs):
            logging.getLogger("httpx").info("private provider URL %s", ISSUER)
            logging.getLogger("httpcore.connection").debug("private connection %s", ISSUER)
            return Stream()
    monkeypatch.setattr("app.oidc_verifier.httpx.Client", Client)
    with caplog.at_level(logging.DEBUG):
        assert MetadataClient(config()).get(config().discovery_url) == {}
        logging.getLogger("httpx").info("legacy-sdk-log-preserved")
    assert ISSUER not in caplog.text
    assert "legacy-sdk-log-preserved" in caplog.text
