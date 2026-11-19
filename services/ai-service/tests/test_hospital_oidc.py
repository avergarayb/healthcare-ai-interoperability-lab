"""Negative checks for the hospital OIDC decision."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
import sqlite3
from cryptography.hazmat.primitives.asymmetric import rsa

from app.config import Settings
from app.critical_lab.http import decide_critical
from app.critical_lab.store import save_proposal
from app.hospital_identity import bindings, persistent_actor, verify_token
from starlette.requests import Request


ISSUER = "http://127.0.0.1:18340/realms/hospital-lab"
AUDIENCE = "mini-his-web"
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _token(username, organization, roles, *, issuer=ISSUER, audience=AUDIENCE, expires=None, key=KEY):
    now = datetime.now(timezone.utc)
    return jwt.encode({
        "iss": issuer,
        "aud": audience,
        "sub": "subject-" + username,
        "preferred_username": username,
        "organization": organization,
        "realm_access": {"roles": roles},
        "iat": now,
        "exp": expires or now + timedelta(minutes=5),
    }, key, algorithm="RS256")


def _settings(**overrides):
    values = dict(
        model_boundary_base_url="http://127.0.0.1:9",
        model_boundary_path="/api/model-boundary/v1",
        model_boundary_timeout_seconds=2,
        model_boundary_service_token="hospital-service-token",
        host="127.0.0.1",
        port=8090,
        hospital_oidc_required=True,
        hospital_oidc_issuer=ISSUER,
        hospital_oidc_audience=AUDIENCE,
        hospital_oidc_jwks_uri=ISSUER + "/protocol/openid-connect/certs",
    )
    values.update(overrides)
    return Settings(**values)


def _request(token="", service="hospital-service-token"):
    headers = {b"x-service-token": service.encode()}
    if token:
        headers[b"x-hospital-identity"] = token.encode()
    return Request({"type": "http", "headers": list(headers.items()), "method": "POST", "path": "/"})


def test_token_negative_matrix_and_bindings_match_the_repository():
    repository = Path(__file__).resolve().parents[3] / "infra" / "healthcare-security-001" / "bindings.json"
    assert json.loads(repository.read_text(encoding="utf-8")) == bindings()
    public = KEY.public_key()
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    identity = verify_token(
        _token("revisor.his", "org-mini-his", ["clinical-reviewer"]),
        issuer=ISSUER, audience=AUDIENCE, bindings_map=bindings(), key=public)
    assert identity.role == "clinical-reviewer"
    assert identity.organization_id == "org-mini-his"
    for token, code, status in (
        (_token("revisor.his", "org-mini-his", ["clinical-reviewer"], key=other), "invalid_token", 401),
        (_token("revisor.his", "org-mini-his", ["clinical-reviewer"], expires=datetime.now(timezone.utc) - timedelta(minutes=1)), "invalid_token", 401),
        (_token("revisor.his", "org-mini-his", ["clinical-reviewer"], issuer="http://127.0.0.1:9/realms/other"), "invalid_token", 401),
        (_token("revisor.his", "org-mini-his", ["clinical-reviewer"], audience="mini-lis-web"), "invalid_token", 401),
        (_token("revisor.his", "org-pe-lab-demo", ["clinical-reviewer"]), "organization_denied", 403),
        (_token("reviewer-pe", "org-pe-lab-demo", ["clinical-reviewer"]), "organization_denied", 403),
        (_token("medico.his", "org-mini-his", ["auditor"]), "role_denied", 403),
    ):
        try:
            verify_token(token, issuer=ISSUER, audience=AUDIENCE, bindings_map=bindings(), key=public)
        except Exception as error:
            assert error.code == code
            assert error.status == status
        else:
            raise AssertionError(code)
    assert persistent_actor("auditor.his", "org-mini-his") is False
    assert persistent_actor("revisor.his", "org-mini-his") is True
    assert persistent_actor("clinica", "org-mini-his") is True


def test_service_token_alone_cannot_approve_and_a_forged_actor_is_ignored(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.critical_lab.http.gate",
        lambda headers, settings, allowed, key=None: __import__("app.hospital_identity", fromlist=["gate"]).gate(
            headers, settings, allowed, key=KEY.public_key()))
    path = tmp_path / "critical.sqlite3"
    prepared = save_proposal(path, "MHS-LAB-1", {"orderId": "MHS-LAB-1"})
    missing = decide_critical(_request(), _settings(), b"{}", path)
    assert missing.status_code == 401
    assert b"hospital-service-token" not in missing.body
    forged = _token("revisor.his", "org-mini-his", ["clinical-reviewer"])
    body = json.dumps({
        "proposalId": prepared["proposalId"],
        "proposalHash": prepared["proposalHash"],
        "decision": "approved",
        "actorId": "auditor.his",
        "role": "auditor",
        "organizationId": "org-pe-lab-demo",
        "idempotencyKey": "once",
    }).encode()
    recorded = decide_critical(_request(forged), _settings(), body, path)
    assert recorded.status_code == 200
    assert forged.encode() not in recorded.body
    assert sqlite3.connect(path).execute("select actor_id from critical_decision").fetchone()[0] == "revisor.his"
    again = decide_critical(_request(forged), _settings(), body.replace(b"once", b"twice"), path)
    assert json.loads(again.body)["outcome"] == "already_decided"
    changed = json.dumps({
        "proposalId": prepared["proposalId"], "proposalHash": "0" * 64, "decision": "approved",
        "actorId": "auditor.his", "role": "auditor", "organizationId": "org-pe-lab-demo",
        "idempotencyKey": "hash",
    }).encode()
    mismatch = decide_critical(_request(forged), _settings(), changed, path)
    assert json.loads(mismatch.body)["outcome"] == "invalid_approval"
    auditor = _token("auditor.his", "org-mini-his", ["auditor"])
    denied = decide_critical(_request(auditor), _settings(), body.replace(b"once", b"role"), path)
    assert denied.status_code == 403
    from app.hospital_identity import authority
    closed_issuer = "http://127.0.0.1:9/realms/hospital-lab"
    unavailable = authority(
        {"x-hospital-identity": _token("revisor.his", "org-mini-his", ["clinical-reviewer"], issuer=closed_issuer)},
        _settings(hospital_oidc_issuer=closed_issuer, hospital_oidc_jwks_uri=closed_issuer + "/protocol/openid-connect/certs"))
    assert unavailable["status"] == 503
    assert unavailable["error"] == "identity_unavailable"
