"""OIDC authorization for laboratory review. No model call and no development bypass."""
import hashlib
import json
import sqlite3
import time

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app.clinical_lab_summary.iam import IamRejected, load_config
from app.clinical_lab_summary.review import (
    assign_review_organization, prepare_decision_store, prepare_organization_store, queue_summary,
)
from app.config import Settings
from app.main import app, get_settings

ISSUER = "http://127.0.0.1:18294/realms/lab-review-iam"
CLIENT = "lab-review-web"
REDIRECT = "http://127.0.0.1:18293/lab-review-iam/callback"
NOW = int(time.time())
REVIEW_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1"
REVIEW_B = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa2"
ORIGIN = {"origin": "http://127.0.0.1:18293"}
SUMMARY = {
    "kind": "lab-result-summary-v1",
    "review": "pending_human_review",
    "statements": [{"text": "GLU 141 mmol/L", "sources": [
        {"source": "mini-lis", "resourceType": "Observation", "id": "MLS-RES-OLD"},
    ]}],
}


def _key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _public(key):
    value = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    value.update(kid="lab-review", alg="RS256", use="sig")
    return value


def _settings(tmp_path, bindings, *, development=False):
    return Settings(
        model_boundary_base_url="http://model-boundary.test",
        model_boundary_path="/api/model-boundary/v1",
        model_boundary_timeout_seconds=5,
        model_boundary_service_token="synthetic-service-token-a",
        human_review_form_signing_secret="synthetic-form-signing-secret-b",
        host="127.0.0.1",
        port=18293,
        ai_review_db_path=str(tmp_path / "follow-up.sqlite3"),
        institutional_knowledge_db_path=str(tmp_path / "knowledge.sqlite3"),
        human_session_db_path=str(tmp_path / "human-session.sqlite3"),
        human_review_development_auth_enabled=development,
        human_review_development_auth_secret="development-secret-value-32chars-min",
        human_review_development_principal_id="lab-reviewer",
        human_review_development_principal_display_name="Lab reviewer",
        lab_summary_review_db_path=str(tmp_path / "review.sqlite3"),
        lab_review_iam_enabled=True,
        lab_review_iam_issuer=ISSUER,
        lab_review_iam_discovery_url=ISSUER + "/.well-known/openid-configuration",
        lab_review_iam_jwks_uri=ISSUER + "/protocol/openid-connect/certs",
        lab_review_iam_client_id=CLIENT,
        lab_review_iam_redirect_uri=REDIRECT,
        lab_review_iam_bindings_path=str(bindings),
        lab_review_iam_session_db_path=str(tmp_path / "iam-session.sqlite3"),
        lab_review_iam_allow_http_loopback=True,
    )


def _bindings(tmp_path, extra=None):
    rows = [
        {"sub": "reviewer-a", "organization_id": "org-lab-a", "role": "clinical-reviewer", "display_name": "Reviewer A"},
        {"sub": "auditor-a", "organization_id": "org-lab-a", "role": "clinical-auditor", "display_name": "Auditor A"},
        {"sub": "admin-a", "organization_id": "org-lab-a", "role": "clinical-admin", "display_name": "Admin A", "grants": ["read"]},
        {"sub": "reviewer-b", "organization_id": "org-lab-b", "role": "clinical-reviewer", "display_name": "Reviewer B"},
    ]
    if extra:
        rows.extend(extra if isinstance(extra, list) else [extra])
    path = tmp_path / "bindings.json"
    path.write_text(json.dumps({"issuer": ISSUER, "bindings": rows}), encoding="utf-8")
    return path


def _seed(path):
    queue_summary(path, REVIEW_A, "demo-auth-a", "MHS-PAT-001", SUMMARY)
    queue_summary(path, REVIEW_B, "demo-auth-b", "MHS-PAT-009", SUMMARY)
    prepare_organization_store(path)
    prepare_decision_store(path)
    assign_review_organization(path, REVIEW_A, "org-lab-a")
    assign_review_organization(path, REVIEW_B, "org-lab-b")


def _token(key, subject, nonce, **changes):
    claims = {
        "iss": ISSUER, "sub": subject, "aud": CLIENT, "iat": NOW, "exp": NOW + 300,
        "nonce": nonce, "azp": CLIENT,
    }
    claims.update(changes)
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "lab-review"})


def _client(tmp_path, key, subject="reviewer-a", extra=None):
    bindings = _bindings(tmp_path, extra)
    settings = _settings(tmp_path, bindings)
    issued = {}
    discovery = {
        "issuer": ISSUER,
        "authorization_endpoint": ISSUER + "/protocol/openid-connect/auth",
        "token_endpoint": ISSUER + "/protocol/openid-connect/token",
        "jwks_uri": ISSUER + "/protocol/openid-connect/certs",
        "end_session_endpoint": ISSUER + "/protocol/openid-connect/logout",
    }

    def handler(request):
        if request.url.path.endswith("openid-configuration"):
            return httpx.Response(200, json=discovery)
        if request.url.path.endswith("certs"):
            return httpx.Response(200, json={"keys": [_public(key)]})
        if request.url.path.endswith("token"):
            return httpx.Response(200, json={"id_token": issued["token"], "token_type": "Bearer"})
        return httpx.Response(404)

    if not (tmp_path / "review.sqlite3").exists():
        _seed(tmp_path / "review.sqlite3")
    app.dependency_overrides[get_settings] = lambda: settings
    app.state.lab_review_iam_clock = lambda: NOW
    app.state.lab_review_iam_http = httpx.Client(transport=httpx.MockTransport(handler))
    client = TestClient(app, base_url="http://127.0.0.1:18293")
    started = client.post("/lab-review-iam/start", headers=ORIGIN, follow_redirects=False)
    state = client.cookies.get("lab_review_iam_tx")
    digest = hashlib.sha256(state.encode("utf-8")).hexdigest()
    with sqlite3.connect(tmp_path / "iam-session.sqlite3") as connection:
        nonce = connection.execute(
            "SELECT nonce FROM iam_transaction WHERE state_hash=?", (digest,)).fetchone()[0]
    issued["token"] = _token(key, subject, nonce)
    issued["state"] = state
    issued["started"] = started
    _trust_loopback(client)
    return client, issued, settings


def _trust_loopback(client):
    """Match a browser on 127.0.0.1, which stores a Secure cookie over HTTP."""
    for cookie in client.cookies.jar:
        if cookie.domain == "127.0.0.1":
            cookie.secure = False


def _login(client, issued, code="synthetic-code"):
    _trust_loopback(client)
    return client.post(
        "/lab-review-iam/callback",
        content=("state=" + issued["state"] + "&code=" + code).encode(),
        headers={"content-type": "application/x-www-form-urlencoded"},
        follow_redirects=False)


@pytest.fixture(autouse=True)
def _clear():
    yield
    app.dependency_overrides.clear()
    if hasattr(app.state, "lab_review_iam_clock"):
        del app.state.lab_review_iam_clock
    if hasattr(app.state, "lab_review_iam_http"):
        del app.state.lab_review_iam_http


def test_authorization_code_login_filters_by_organization(tmp_path):
    key = _key()
    before = (tmp_path / "review.sqlite3")
    client, issued, _settings_value = _client(tmp_path, key)
    assert issued["started"].status_code == 303
    transaction = issued["started"].headers["set-cookie"]
    assert "lab_review_iam_tx=" in transaction
    assert "HttpOnly" in transaction and "SameSite=none" in transaction and "Secure" in transaction
    assert "code_challenge_method=S256" in issued["started"].headers["location"]
    assert "response_mode=form_post" in issued["started"].headers["location"]
    callback = _login(client, issued)
    assert callback.status_code == 303
    assert callback.headers["location"] == "/lab-summaries"
    page = client.get("/lab-summaries")
    assert page.status_code == 200
    assert "Reviewer A" in page.text and "org-lab-a" in page.text and "clinical-reviewer" in page.text
    assert "MHS-PAT-001" in page.text
    assert "MHS-PAT-009" not in page.text
    forged = client.get("/lab-summaries?organizacion=org-lab-b")
    assert "MHS-PAT-009" not in forged.text
    other = client.get("/lab-summaries/" + REVIEW_B)
    assert other.status_code == 403
    original = sqlite3.connect(before).execute(
        "SELECT summary_json, status FROM lab_summary_review WHERE review_id=?", (REVIEW_A,)).fetchone()
    assert original[1] == "pending" and "GLU 141 mmol/L" in original[0]


def test_unauthenticated_invalid_and_replayed_login_are_rejected(tmp_path):
    key = _key()
    client, issued, _settings_value = _client(tmp_path, key)
    anonymous = TestClient(app, base_url="http://127.0.0.1:18293")
    assert anonymous.get("/lab-summaries", follow_redirects=False).status_code == 303
    issued["token"] = _token(_key(), "reviewer-a", "wrong-nonce")
    # The stored nonce will not match this replacement token.
    denied = _login(client, issued)
    assert denied.status_code == 303 and "denied" in denied.headers["location"]
    client, issued, _settings_value = _client(tmp_path, key)
    assert _login(client, issued).status_code == 303
    replay = _login(client, issued)
    assert replay.status_code == 303 and "denied" in replay.headers["location"]
    client, issued, _settings_value = _client(tmp_path, key)
    leaked = client.get(
        "/lab-review-iam/callback",
        params={"code": "synthetic-code", "state": issued["state"]},
        follow_redirects=False)
    assert leaked.status_code == 303 and "denied" in leaked.headers["location"]
    assert "code=" not in leaked.headers["location"]
    assert _login(client, issued).headers["location"] == "/lab-summaries"
    client, issued, _settings_value = _client(tmp_path, key)
    claims = jwt.decode(
        issued["token"], key.public_key(), algorithms=["RS256"], audience=CLIENT, issuer=ISSUER)
    claims["iss"] = "https://issuer.example/realms/other"
    issued["token"] = jwt.encode(claims, key, algorithm="RS256", headers={"kid": "lab-review"})
    assert "denied" in _login(client, issued).headers["location"]
    client, issued, _settings_value = _client(tmp_path, key)
    claims = jwt.decode(
        issued["token"], key.public_key(), algorithms=["RS256"], audience=CLIENT, issuer=ISSUER)
    claims["iat"] = NOW - 400
    claims["exp"] = NOW - 120
    issued["token"] = jwt.encode(claims, key, algorithm="RS256", headers={"kid": "lab-review"})
    assert "denied" in _login(client, issued).headers["location"]


def test_expired_wrong_audience_and_csrf_are_rejected(tmp_path):
    key = _key()
    client, issued, _settings_value = _client(tmp_path, key)
    issued["token"] = jwt.encode(
        {"iss": ISSUER, "sub": "reviewer-a", "aud": "other-client", "iat": NOW, "exp": NOW + 300,
         "nonce": "ignored"},
        key, algorithm="RS256", headers={"kid": "lab-review"})
    # Nonce is also wrong, so the callback closes.
    assert "denied" in _login(client, issued).headers["location"]
    client, issued, _settings_value = _client(tmp_path, key)
    assert _login(client, issued).status_code == 303
    app.state.lab_review_iam_clock = lambda: NOW + 1801
    expired = client.get("/lab-summaries", follow_redirects=False)
    assert expired.status_code == 303 and "expired" in expired.headers["location"]
    app.state.lab_review_iam_clock = lambda: NOW
    detail = client.get("/lab-summaries/" + REVIEW_A)
    csrf = detail.text.split('name="csrf" value="', 1)[1].split('"', 1)[0]
    missing = client.post(
        "/lab-summaries/" + REVIEW_A + "/decision",
        content=b"decision=approved&note=sintetica",
        headers={"content-type": "application/x-www-form-urlencoded", **ORIGIN})
    assert missing.status_code == 422
    forged = client.post(
        "/lab-summaries/" + REVIEW_A + "/decision",
        content=("decision=approved&note=sintetica&csrf=" + csrf + "&role=clinical-admin&organization_id=org-lab-b").encode(),
        headers={"content-type": "application/x-www-form-urlencoded", **ORIGIN})
    assert forged.status_code == 422
    cross = client.post(
        "/lab-summaries/" + REVIEW_A + "/decision",
        content=("decision=approved&note=sintetica&csrf=" + csrf).encode(),
        headers={"content-type": "application/x-www-form-urlencoded", "origin": "http://evil.example"})
    assert cross.status_code == 403
    accepted = client.post(
        "/lab-summaries/" + REVIEW_A + "/decision",
        content=("decision=approved&note=Cifra%20sintetica&csrf=" + csrf).encode(),
        headers={"content-type": "application/x-www-form-urlencoded", **ORIGIN},
        follow_redirects=False)
    assert accepted.status_code == 303
    confirmed = client.get("/lab-summaries/" + REVIEW_A)
    assert ISSUER in confirmed.text and "reviewer-a" in confirmed.text and "approved" in confirmed.text
    again = client.post(
        "/lab-summaries/" + REVIEW_A + "/decision",
        content=("decision=rejected&note=tarde&csrf=" + csrf).encode(),
        headers={"content-type": "application/x-www-form-urlencoded", **ORIGIN})
    assert again.status_code == 409
    status = sqlite3.connect(tmp_path / "review.sqlite3").execute(
        "SELECT status FROM lab_summary_review WHERE review_id=?", (REVIEW_A,)).fetchone()[0]
    assert status == "pending"


def test_auditor_and_admin_cannot_approve_and_logout_ends_access(tmp_path):
    key = _key()
    client, issued, _settings_value = _client(tmp_path, key, "auditor-a")
    assert _login(client, issued).status_code == 303
    page = client.get("/lab-summaries/" + REVIEW_A)
    assert "no incluye aprobar" in page.text
    assert "Aprobar" not in page.text
    csrf = page.text.split('name="csrf" value="', 1)[1].split('"', 1)[0]
    denied = client.post(
        "/lab-summaries/" + REVIEW_A + "/decision",
        content=("decision=approved&note=no&csrf=" + csrf).encode(),
        headers={"content-type": "application/x-www-form-urlencoded", **ORIGIN})
    assert denied.status_code == 403
    logged_out = client.post(
        "/lab-review-iam/logout",
        content=("csrf=" + csrf).encode(),
        headers={"content-type": "application/x-www-form-urlencoded", **ORIGIN},
        follow_redirects=False)
    assert logged_out.status_code == 303
    assert "openid-connect/logout" in logged_out.headers["location"]
    assert "id_token" not in logged_out.headers["location"]
    assert client.get("/lab-summaries", follow_redirects=False).status_code == 303
    admin, admin_issued, _settings_value = _client(tmp_path, key, "admin-a")
    assert _login(admin, admin_issued).status_code == 303
    queue = admin.get("/lab-summaries")
    assert "MHS-PAT-001" in queue.text
    detail = admin.post(
        "/lab-summaries/" + REVIEW_A + "/decision",
        content=b"decision=approved&note=admin&csrf=not-the-token",
        headers={"content-type": "application/x-www-form-urlencoded", **ORIGIN})
    assert detail.status_code == 403


def test_development_authentication_cannot_bypass_iam(tmp_path):
    bindings = _bindings(tmp_path)
    settings = _settings(tmp_path, bindings, development=True)
    app.dependency_overrides[get_settings] = lambda: settings
    with pytest.raises(IamRejected) as error:
        load_config(settings)
    assert error.value.reason == "development_bypass_rejected"
    client = TestClient(app, base_url="http://127.0.0.1:18293")
    assert client.get("/lab-summaries").status_code == 503
    dangerous = tmp_path / "bad.json"
    dangerous.write_text(json.dumps({"issuer": ISSUER, "bindings": [
        {"sub": "admin-danger", "organization_id": "org-lab-a", "role": "clinical-admin",
         "display_name": "Danger", "grants": ["decide"]},
    ]}), encoding="utf-8")
    with pytest.raises(IamRejected):
        load_config(_settings(tmp_path, dangerous))


def test_unknown_subject_is_not_authorized(tmp_path):
    key = _key()
    client, issued, _settings_value = _client(tmp_path, key, "not-bound")
    assert "denied" in _login(client, issued).headers["location"]
