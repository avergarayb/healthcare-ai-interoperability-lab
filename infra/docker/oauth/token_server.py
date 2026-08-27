#!/usr/bin/env python3
"""Synthetic OAuth 2.0 / SMART on FHIR Authorization Server for the lab."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

CLIENT_ID = os.environ.get("LAB_OAUTH_CLIENT_ID", "lab-client")
CLIENT_SECRET = os.environ.get("LAB_OAUTH_CLIENT_SECRET", "lab-secret")
ACCESS_TOKEN = os.environ.get("LAB_OAUTH_ACCESS_TOKEN", "lab-access-token")
EXPIRES_IN = int(os.environ.get("LAB_OAUTH_EXPIRES_IN", "3600"))

SMART_CLIENT_ID = os.environ.get("LAB_SMART_CLIENT_ID", "lab-smart-app")
SMART_REDIRECT_URI = os.environ.get(
    "LAB_SMART_REDIRECT_URI", "http://127.0.0.1:8081/smart/callback"
)
SMART_AUD = os.environ.get("LAB_SMART_AUD", "http://localhost:8180/fhir")
SMART_PATIENT = os.environ.get("LAB_SMART_PATIENT", "patient-001")
SMART_SCOPES = (
    "patient/Patient.read",
    "patient/Observation.read",
    "patient/Condition.read",
    "user/Patient.read",
    "system/Patient.read",
)

LOCK = threading.Lock()
AUTH_CODES: dict[str, dict] = {}
ACCESS_TOKENS: dict[str, dict] = {}
REFRESH_TOKENS: dict[str, dict] = {}


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _pkce_s256(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return _b64url(digest)


def _normalize_aud(value: str) -> str:
    return (value or "").rstrip("/")


def _new_token() -> str:
    return "smart-" + secrets.token_urlsafe(24)


class TokenHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        super().log_message(format, *args)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/.well-known/smart-configuration":
            self._smart_configuration()
            return
        if path == "/authorize":
            self._authorize()
            return
        if path == "/oauth/resource":
            self._authorize_resource()
            return
        self._json(404, {"error": "not_found"})

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/oauth/token":
            self._token()
            return
        if path == "/oauth/resource":
            self._authorize_resource()
            return
        self._json(404, {"error": "not_found"})

    def do_PUT(self):
        if urlparse(self.path).path == "/oauth/resource":
            self._authorize_resource()
            return
        self._json(404, {"error": "not_found"})

    def do_DELETE(self):
        if urlparse(self.path).path == "/oauth/resource":
            self._authorize_resource()
            return
        self._json(404, {"error": "not_found"})

    def _smart_configuration(self):
        self._json(
            200,
            {
                "authorization_endpoint": "http://localhost:9090/authorize",
                "token_endpoint": "http://localhost:9090/oauth/token",
                "grant_types_supported": [
                    "authorization_code",
                    "refresh_token",
                    "client_credentials",
                ],
                "response_types_supported": ["code"],
                "code_challenge_methods_supported": ["S256"],
                "scopes_supported": list(SMART_SCOPES),
                "token_endpoint_auth_methods_supported": ["none", "client_secret_post"],
                "capabilities": [
                    "launch-standalone",
                    "client-public",
                    "permission-patient",
                    "context-standalone-patient",
                ],
            },
        )

    def _authorize(self):
        query = parse_qs(urlparse(self.path).query, keep_blank_values=True)
        params = {key: values[0] if values else "" for key, values in query.items()}
        if params.get("response_type") != "code":
            self._json(400, {"error": "unsupported_response_type"})
            return
        if params.get("client_id") != SMART_CLIENT_ID:
            self._json(401, {"error": "invalid_client"})
            return
        if params.get("redirect_uri") != SMART_REDIRECT_URI:
            self._json(400, {"error": "invalid_request"})
            return
        if _normalize_aud(params.get("aud", "")) != _normalize_aud(SMART_AUD):
            self._json(400, {"error": "invalid_request"})
            return
        if params.get("code_challenge_method") != "S256":
            self._json(400, {"error": "invalid_request"})
            return
        challenge = params.get("code_challenge", "")
        state = params.get("state", "")
        if not challenge or not state:
            self._json(400, {"error": "invalid_request"})
            return
        requested = {item for item in params.get("scope", "").split() if item}
        granted = " ".join(scope for scope in SMART_SCOPES if scope in requested) or "patient/Patient.read"
        code = secrets.token_urlsafe(24)
        with LOCK:
            AUTH_CODES[code] = {
                "client_id": SMART_CLIENT_ID,
                "redirect_uri": SMART_REDIRECT_URI,
                "code_challenge": challenge,
                "scope": granted,
                "patient": SMART_PATIENT,
                "used": False,
            }
        location = SMART_REDIRECT_URI + "?" + urlencode({"code": code, "state": state})
        self.send_response(302)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _token(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8")
        params = {key: values[0] if values else "" for key, values in parse_qs(raw, keep_blank_values=True).items()}
        grant_type = params.get("grant_type", "")
        if grant_type == "client_credentials":
            self._client_credentials(params)
            return
        if grant_type == "authorization_code":
            self._authorization_code(params)
            return
        if grant_type == "refresh_token":
            self._refresh(params)
            return
        self._json(400, {"error": "unsupported_grant_type"})

    def _client_credentials(self, params: dict[str, str]) -> None:
        client_id, client_secret = self._client_credentials_from(params)
        if not client_id or not client_secret:
            self._json(400, {"error": "invalid_request"})
            return
        if client_id != CLIENT_ID or client_secret != CLIENT_SECRET:
            self._json(401, {"error": "invalid_client"})
            return
        self._json(
            200,
            {
                "access_token": ACCESS_TOKEN,
                "token_type": "Bearer",
                "expires_in": EXPIRES_IN,
            },
        )

    def _authorization_code(self, params: dict[str, str]) -> None:
        code = params.get("code", "")
        verifier = params.get("code_verifier", "")
        redirect_uri = params.get("redirect_uri", "")
        client_id = params.get("client_id", "")
        if not code or not verifier or not redirect_uri or not client_id:
            self._json(400, {"error": "invalid_request"})
            return
        with LOCK:
            stored = AUTH_CODES.get(code)
            if stored is None or stored["used"]:
                self._json(400, {"error": "invalid_grant"})
                return
            if stored["client_id"] != client_id or stored["redirect_uri"] != redirect_uri:
                self._json(400, {"error": "invalid_grant"})
                return
            if _pkce_s256(verifier) != stored["code_challenge"]:
                self._json(400, {"error": "invalid_grant"})
                return
            stored["used"] = True
            payload = self._issue_smart_tokens(stored["scope"], stored["patient"])
        self._json(200, payload)

    def _refresh(self, params: dict[str, str]) -> None:
        refresh = params.get("refresh_token", "")
        client_id = params.get("client_id", "")
        if not refresh or not client_id:
            self._json(400, {"error": "invalid_request"})
            return
        with LOCK:
            stored = REFRESH_TOKENS.get(refresh)
            if stored is None or stored["client_id"] != client_id:
                self._json(400, {"error": "invalid_grant"})
                return
            del REFRESH_TOKENS[refresh]
            payload = self._issue_smart_tokens(stored["scope"], stored["patient"])
        self._json(200, payload)

    def _issue_smart_tokens(self, scope: str, patient: str) -> dict:
        access = _new_token()
        refresh = "refresh-" + secrets.token_urlsafe(24)
        record = {
            "scope": scope,
            "patient": patient,
            "client_id": SMART_CLIENT_ID,
            "expires_at": time.time() + EXPIRES_IN,
        }
        ACCESS_TOKENS[access] = record
        REFRESH_TOKENS[refresh] = {
            "scope": scope,
            "patient": patient,
            "client_id": SMART_CLIENT_ID,
        }
        return {
            "access_token": access,
            "token_type": "Bearer",
            "expires_in": EXPIRES_IN,
            "refresh_token": refresh,
            "scope": scope,
            "patient": patient,
        }

    def _authorize_resource(self) -> None:
        header = self.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            self.send_error_status(401, {"error": "invalid_token"})
            return
        token = header[7:].strip()
        uri = self.headers.get("X-Original-URI", "")
        method = (self.headers.get("X-Original-Method") or "GET").upper()
        if token == ACCESS_TOKEN:
            self.send_response(200)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        with LOCK:
            stored = ACCESS_TOKENS.get(token)
        if stored is None or stored["expires_at"] <= time.time():
            self.send_error_status(401, {"error": "invalid_token"})
            return
        if not self._scope_allows(stored["scope"], stored["patient"], method, uri):
            self.send_error_status(403, {"error": "insufficient_scope"})
            return
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _scope_allows(self, scope: str, patient: str, method: str, uri: str) -> bool:
        parsed = urlparse(uri)
        path = parsed.path
        if path in ("/fhir/metadata", "/fhir/.well-known/smart-configuration"):
            return True
        resource = self._resource_type(path)
        if resource is None:
            return False
        if method != "GET":
            return False
        granted = set(scope.split())
        allowed = {
            f"patient/{resource}.read",
            f"user/{resource}.read",
            f"system/{resource}.read",
            "system/*.read",
        }
        if granted.isdisjoint(allowed):
            return False
        requested_patient = self._requested_patient(path, parsed.query)
        if patient and requested_patient and requested_patient != patient:
            return False
        return True

    def _resource_type(self, path: str) -> str | None:
        parts = [part for part in path.split("/") if part]
        if not parts or parts[0] != "fhir" or len(parts) < 2:
            return None
        return parts[1]

    def _requested_patient(self, path: str, query: str) -> str:
        parts = [part for part in path.split("/") if part]
        if len(parts) >= 3 and parts[1] == "Patient":
            return parts[2]
        params = parse_qs(query)
        subject = params.get("patient", [""])[0]
        if subject.startswith("Patient/"):
            return subject.split("/", 1)[1]
        return subject

    def _client_credentials_from(self, params: dict[str, str]) -> tuple[str, str]:
        client_id = params.get("client_id", "")
        client_secret = params.get("client_secret", "")
        header = self.headers.get("Authorization", "")
        if header.startswith("Basic "):
            try:
                decoded = base64.b64decode(header[6:]).decode("utf-8")
                basic_id, basic_secret = decoded.split(":", 1)
                client_id = client_id or basic_id
                client_secret = client_secret or basic_secret
            except (ValueError, UnicodeDecodeError):
                return client_id, client_secret
        return client_id, client_secret

    def send_error_status(self, status: int, payload: dict) -> None:
        self._json(status, payload)

    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 9090), TokenHandler).serve_forever()
