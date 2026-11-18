"""Laboratory OIDC session for lab-summary review.

The ID token proves one issuer and subject. Organization and role come from the
server binding file. A browser field, a token role, or a patient identifier
cannot choose either. This is not production healthcare certification.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import secrets
import sqlite3
import ssl
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode, urlsplit, urlunsplit

import httpx
import jwt

from app.config import Settings


AUTHENTICATOR_ID = "LAB_REVIEW_IAM_V1"
SESSION_COOKIE = "lab_review_iam"
TRANSACTION_COOKIE = "lab_review_iam_tx"
SESSION_TTL_SECONDS = 1800
TRANSACTION_TTL_SECONDS = 300
_LOOPBACK = {"127.0.0.1", "::1"}
_ROLES = {"clinical-reviewer", "clinical-auditor", "clinical-admin"}
_ROLE_PERMISSIONS = {
    "clinical-reviewer": frozenset({"read", "decide", "audit"}),
    "clinical-auditor": frozenset({"read", "audit"}),
    "clinical-admin": frozenset(),
}
_ADMIN_GRANTS = frozenset({"read", "audit"})
_ORG_ID = re.compile(r"^org-[a-z0-9](?:[a-z0-9-]{0,30}[a-z0-9])?$")
_SUBJECT = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_ISSUER = re.compile(r"^https?://127\.0\.0\.1:[0-9]{2,5}/realms/[A-Za-z0-9_-]{1,64}$|^https://[A-Za-z0-9._:-]{1,200}/realms/[A-Za-z0-9_-]{1,64}$")
_DNS_HOST = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$")


class IamRejected(Exception):
    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True)
class Binding:
    subject: str
    organization_id: str
    role: str
    display_name: str
    permissions: frozenset


@dataclass(frozen=True)
class IamConfig:
    issuer: str
    discovery_url: str
    jwks_uri: str
    client_id: str
    redirect_uri: str
    bindings: dict
    session_db_path: str
    allow_http_loopback: bool


@dataclass(frozen=True)
class IamSession:
    session_id: str
    issuer: str
    subject: str
    organization_id: str
    role: str
    display_name: str
    permissions: frozenset
    csrf: str
    expires_at: int


def load_config(settings: Settings) -> IamConfig:
    if not settings.lab_review_iam_enabled:
        raise IamRejected("iam_disabled")
    if settings.human_review_development_auth_enabled:
        raise IamRejected("development_bypass_rejected")
    if settings.host not in _LOOPBACK:
        raise IamRejected("host_rejected")
    issuer = settings.lab_review_iam_issuer
    discovery = settings.lab_review_iam_discovery_url
    jwks = settings.lab_review_iam_jwks_uri
    client_id = settings.lab_review_iam_client_id
    redirect = settings.lab_review_iam_redirect_uri
    if (_ISSUER.fullmatch(issuer) is None or not discovery.startswith(issuer + "/.well-known/")
            or not jwks.startswith(issuer + "/") or not 1 <= len(client_id) <= 128):
        raise IamRejected("configuration_rejected")
    _require_redirect(redirect, settings.lab_review_iam_allow_http_loopback)
    _require_loopback_http(
        issuer, discovery, jwks, allow_http=settings.lab_review_iam_allow_http_loopback)
    session_path = settings.lab_review_iam_session_db_path
    if (not session_path or session_path in {":memory:", settings.lab_summary_review_db_path,
                                             settings.human_session_db_path, settings.ai_review_db_path}):
        raise IamRejected("configuration_rejected")
    bindings = _bindings(settings.lab_review_iam_bindings_path, issuer)
    return IamConfig(issuer, discovery, jwks, client_id, redirect, bindings, session_path,
                     settings.lab_review_iam_allow_http_loopback)


def begin_authentication(config: IamConfig, now: int, client: httpx.Client | None = None) -> tuple[str, str]:
    metadata = _discovery(config, client)
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")
    _transaction_store(config).save(state, verifier, nonce, now + TRANSACTION_TTL_SECONDS)
    query = urlencode({
        "response_type": "code",
        "response_mode": "form_post",
        "client_id": config.client_id,
        "redirect_uri": config.redirect_uri,
        "scope": "openid",
        "state": state,
        "nonce": nonce,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    })
    return metadata["authorization_endpoint"] + "?" + query, state


def complete_authentication(config: IamConfig, state: str, code: str, now: int, client: httpx.Client) -> tuple[str, IamSession]:
    if not isinstance(state, str) or not isinstance(code, str) or not 1 <= len(code) <= 2048:
        raise IamRejected("state_rejected")
    transaction = _transaction_store(config).take(state, now)
    if transaction is None:
        raise IamRejected("state_rejected")
    metadata = _discovery(config, client)
    response = _post_form(client, config, metadata["token_endpoint"], {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": config.redirect_uri,
        "client_id": config.client_id,
        "code_verifier": transaction["verifier"],
    })
    id_token = response.get("id_token")
    if not isinstance(id_token, str):
        raise IamRejected("token_rejected")
    claims = _verify_id_token(config, id_token, transaction["nonce"], client, now)
    binding = config.bindings.get(claims["sub"])
    if binding is None or claims["iss"] != config.issuer:
        raise IamRejected("binding_denied")
    return _session_store(config).issue(binding, claims["iss"], now)


def resolve_session(config: IamConfig, token: str, now: int) -> IamSession | None:
    stored = _session_store(config).resolve(token, now)
    if stored is None:
        return None
    binding = config.bindings.get(stored.subject)
    if binding is None or binding.organization_id != stored.organization_id or binding.role != stored.role:
        return None
    return IamSession(
        stored.session_id, stored.issuer, stored.subject, stored.organization_id, stored.role,
        binding.display_name, binding.permissions, stored.csrf, stored.expires_at)


def revoke_session(config: IamConfig, token: str, now: int) -> None:
    _session_store(config).revoke(token, now)


def end_session_url(config: IamConfig, client: httpx.Client | None = None) -> str | None:
    document = _discovery(config, client)
    endpoint = document.get("end_session_endpoint")
    if not _same_issuer(config, endpoint):
        return None
    parts = urlsplit(config.redirect_uri)
    return_to = urlunsplit((parts.scheme, parts.netloc, "/lab-review-iam/login", "", ""))
    return endpoint + "?" + urlencode({
        "client_id": config.client_id,
        "post_logout_redirect_uri": return_to,
    })


def _require_redirect(redirect, allow_http):
    parts = urlsplit(redirect)
    if (parts.path != "/lab-review-iam/callback" or parts.query or parts.fragment
            or parts.username or parts.password):
        raise IamRejected("configuration_rejected")
    if parts.hostname == "127.0.0.1":
        if parts.scheme == "https":
            return
        if allow_http and parts.scheme == "http":
            return
        raise IamRejected("configuration_rejected")
    host = parts.hostname or ""
    if parts.scheme != "https" or _DNS_HOST.fullmatch(host) is None:
        raise IamRejected("configuration_rejected")


def _require_loopback_http(*urls, allow_http):
    for url in urls:
        parts = urlsplit(url)
        if parts.scheme == "https":
            continue
        if not (allow_http and parts.scheme == "http" and parts.hostname == "127.0.0.1"):
            raise IamRejected("configuration_rejected")


def _bindings(path, issuer):
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise IamRejected("configuration_rejected") from None
    if not isinstance(document, dict) or document.get("issuer") != issuer or not isinstance(document.get("bindings"), list):
        raise IamRejected("configuration_rejected")
    found = {}
    for item in document["bindings"]:
        binding = _binding(item)
        if binding.subject in found:
            raise IamRejected("configuration_rejected")
        found[binding.subject] = binding
    if not found:
        raise IamRejected("configuration_rejected")
    return found


def _binding(item):
    if not isinstance(item, dict):
        raise IamRejected("configuration_rejected")
    subject = item.get("sub")
    organization = item.get("organization_id")
    role = item.get("role")
    display = item.get("display_name")
    grants = item.get("grants", [])
    if (_SUBJECT.fullmatch(subject or "") is None or _ORG_ID.fullmatch(organization or "") is None
            or role not in _ROLES or not isinstance(display, str) or not 1 <= len(display) <= 80
            or any(ord(char) < 32 for char in display) or not isinstance(grants, list)):
        raise IamRejected("configuration_rejected")
    if role == "clinical-admin":
        if any(grant not in _ADMIN_GRANTS for grant in grants):
            raise IamRejected("configuration_rejected")
        permissions = frozenset(grants)
    elif grants:
        raise IamRejected("configuration_rejected")
    else:
        permissions = _ROLE_PERMISSIONS[role]
    return Binding(subject, organization, role, display, permissions)


def _discovery(config, client=None):
    own = client is None
    client = client or _client(config)
    try:
        response = client.get(config.discovery_url, headers={"Accept": "application/json"})
        if response.status_code != 200 or len(response.content) > 1_048_576:
            raise IamRejected("provider_unavailable")
        document = response.json()
    except (httpx.HTTPError, json.JSONDecodeError, ValueError):
        raise IamRejected("provider_unavailable") from None
    finally:
        if own:
            client.close()
    if (document.get("issuer") != config.issuer or document.get("jwks_uri") != config.jwks_uri
            or not _same_issuer(config, document.get("authorization_endpoint"))
            or not _same_issuer(config, document.get("token_endpoint"))):
        raise IamRejected("discovery_rejected")
    return document


def _same_issuer(config, url):
    return isinstance(url, str) and url.startswith(config.issuer + "/")


def _verify_id_token(config, token, nonce, client, now):
    try:
        header = jwt.get_unverified_header(token)
    except jwt.InvalidTokenError:
        raise IamRejected("token_rejected") from None
    if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str):
        raise IamRejected("token_rejected")
    key = _key(config, header["kid"], client)
    try:
        claims = jwt.decode(
            token, key, algorithms=["RS256"], audience=config.client_id, issuer=config.issuer,
            leeway=60, options={"require": ["exp", "iat", "sub", "nonce", "aud", "iss"]},
        )
    except jwt.InvalidTokenError:
        raise IamRejected("token_rejected") from None
    if not isinstance(claims.get("nonce"), str) or claims.get("nonce") != nonce:
        raise IamRejected("nonce_rejected")
    if "azp" in claims and claims.get("azp") != config.client_id:
        raise IamRejected("token_rejected")
    if not isinstance(claims.get("iat"), int) or not isinstance(claims.get("exp"), int):
        raise IamRejected("token_rejected")
    if claims["exp"] - claims["iat"] > 600 or claims["iat"] > now + 60 or claims["exp"] <= now - 60:
        raise IamRejected("token_rejected")
    return claims


def _key(config, kid, client):
    try:
        response = client.get(config.jwks_uri, headers={"Accept": "application/json"})
        document = response.json()
    except (httpx.HTTPError, json.JSONDecodeError, ValueError):
        raise IamRejected("provider_unavailable") from None
    for item in document.get("keys") or []:
        if item.get("kid") == kid and item.get("alg", "RS256") == "RS256" and item.get("use", "sig") == "sig":
            if item.get("kty") != "RSA":
                raise IamRejected("token_rejected")
            key = jwt.PyJWK.from_dict(item).key
            numbers = key.public_numbers()
            if numbers.n.bit_length() < 2048:
                raise IamRejected("token_rejected")
            return key
    raise IamRejected("token_rejected")


def _post_form(client, config, url, form):
    if not _same_issuer(config, url):
        raise IamRejected("discovery_rejected")
    try:
        response = client.post(url, data=form, headers={"Accept": "application/json"})
        if response.status_code != 200:
            raise IamRejected("token_rejected")
        return response.json()
    except (httpx.HTTPError, json.JSONDecodeError, ValueError):
        raise IamRejected("token_rejected") from None


def _client(config):
    verify: bool | ssl.SSLContext = True
    ca_file = os.environ.get("DEMO_CA_FILE", "")
    if ca_file and Path(ca_file).is_file():
        verify = ssl.create_default_context()
        verify.load_verify_locations(cafile=ca_file)
    return httpx.Client(timeout=2.0, trust_env=False, follow_redirects=False, verify=verify)


class _TransactionStore:
    def __init__(self, path):
        self.path = path

    def save(self, state, verifier, nonce, expires_at):
        connection = self._connection()
        try:
            connection.execute(
                "INSERT INTO iam_transaction (state_hash, verifier, nonce, expires_at) VALUES (?, ?, ?, ?)",
                (hashlib.sha256(state.encode("utf-8")).hexdigest(), verifier, nonce, expires_at))
        finally:
            connection.close()

    def take(self, state, now):
        digest = hashlib.sha256(state.encode("utf-8")).hexdigest()
        connection = self._connection()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT verifier, nonce, expires_at FROM iam_transaction WHERE state_hash=?", (digest,)
            ).fetchone()
            connection.execute("DELETE FROM iam_transaction WHERE state_hash=?", (digest,))
            connection.execute("COMMIT")
        finally:
            connection.close()
        if row is None or row[2] < now:
            return None
        return {"verifier": row[0], "nonce": row[1]}

    def _connection(self):
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS iam_transaction (
                state_hash TEXT PRIMARY KEY,
                verifier TEXT NOT NULL,
                nonce TEXT NOT NULL,
                expires_at INTEGER NOT NULL
            )
            """)
        return connection


class _SessionStore:
    def __init__(self, path):
        self.path = path

    def issue(self, binding: Binding, issuer: str, now: int):
        token = secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(32)
        session_id = secrets.token_hex(16)
        expires_at = now + SESSION_TTL_SECONDS
        connection = self._connection()
        try:
            connection.execute(
                "INSERT INTO iam_session (session_id, token_hash, issuer, subject, organization_id, role, "
                "display_name, csrf, issued_at, expires_at, revoked_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)",
                (session_id, hashlib.sha256(token.encode("utf-8")).hexdigest(), issuer, binding.subject,
                 binding.organization_id, binding.role, binding.display_name, csrf, now, expires_at))
        finally:
            connection.close()
        return token, IamSession(session_id, issuer, binding.subject, binding.organization_id, binding.role,
                                 binding.display_name, binding.permissions, csrf, expires_at)

    def resolve(self, token, now):
        if not isinstance(token, str) or not 20 <= len(token) <= 128:
            return None
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        connection = self._connection()
        try:
            row = connection.execute(
                "SELECT session_id, issuer, subject, organization_id, role, display_name, csrf, expires_at, revoked_at "
                "FROM iam_session WHERE token_hash=?", (digest,)
            ).fetchone()
        finally:
            connection.close()
        if row is None or row[8] is not None or row[7] <= now:
            return None
        return IamSession(row[0], row[1], row[2], row[3], row[4], row[5], frozenset(), row[6], row[7])

    def revoke(self, token, now):
        if not isinstance(token, str):
            return
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        connection = self._connection()
        try:
            connection.execute(
                "UPDATE iam_session SET revoked_at=? WHERE token_hash=? AND revoked_at IS NULL", (now, digest))
        finally:
            connection.close()

    def _connection(self):
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS iam_session (
                session_id TEXT PRIMARY KEY,
                token_hash TEXT UNIQUE NOT NULL,
                issuer TEXT NOT NULL,
                subject TEXT NOT NULL,
                organization_id TEXT NOT NULL,
                role TEXT NOT NULL,
                display_name TEXT NOT NULL,
                csrf TEXT NOT NULL,
                issued_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                revoked_at INTEGER
            )
            """)
        return connection


def _transaction_store(config):
    return _TransactionStore(config.session_db_path)


def _session_store(config):
    return _SessionStore(config.session_db_path)


def clock_now(request) -> int:
    clock = getattr(request.app.state, "lab_review_iam_clock", None)
    return int(time.time() if clock is None else clock())
