"""Test-fixture validation only. Never imported by either product service."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

import jwt

REALM = "healthcare-iam-lab"
AI = "healthcare-ai-api"
INTEROP = "healthcare-interop-api"
WEB = "healthcare-review-web"
PROTECTED_PORTS = {8080, 8081, 8095, 8096, 8180, 9090, 15434, 18281, 18290, 18295, 18296}


class Denied(Exception):
    """Only this fixed reason, never a credential or upstream error, is reported."""


class HttpFailure(Exception):
    def __init__(self, status: int, code: str = "http_failure") -> None:
        self.status = status
        self.code = code
        super().__init__(code)


def origin_for(port: int) -> str:
    if not isinstance(port, int) or port < 1024 or port > 65535 or port in PROTECTED_PORTS:
        raise Denied("unsafe_lab_port")
    return f"http://localhost:{port}"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Http:
    """Exact loopback fixture endpoints, no proxies, redirects or dynamic trust."""

    def __init__(self, origin: str) -> None:
        parsed = urllib.parse.urlsplit(origin)
        if origin != origin_for(parsed.port or 0):
            raise Denied("unsafe_lab_origin")
        self.origin = origin
        issuer = origin + "/realms/" + REALM
        self.allowed = {
            issuer + "/.well-known/openid-configuration",
            issuer + "/protocol/openid-connect/certs",
            issuer + "/protocol/openid-connect/token",
        }
        self.opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), NoRedirect()
        )

    def request(self, url: str, form: dict | None = None) -> dict:
        if url not in self.allowed:
            raise Denied("endpoint_not_approved")
        data = None if form is None else urllib.parse.urlencode(form).encode()
        request = urllib.request.Request(url, data=data, headers={"Accept": "application/json"})
        try:
            with self.opener.open(request, timeout=2) as response:
                raw = response.read(1_048_577)
                if len(raw) > 1_048_576:
                    raise Denied("response_too_large")
                result = json.loads(raw)
                if not isinstance(result, dict):
                    raise Denied("invalid_json_response")
                return result
        except urllib.error.HTTPError as exc:
            # Never expose error_description, request bodies or a returned token.
            code = "http_failure"
            try:
                candidate = json.loads(exc.read(4096)).get("error")
                if candidate in {"invalid_scope", "invalid_client", "unauthorized_client", "invalid_grant"}:
                    code = candidate
            except (ValueError, AttributeError):
                pass
            raise HttpFailure(exc.code, code) from None
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            raise HttpFailure(0, "fixture_unavailable") from None


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise Denied("duplicate_json_claim")
        result[key] = value
    return result


def require_access_purpose(verified_claims: dict) -> None:
    """Predicate for already cryptographically verified claims; never a JWT verifier."""
    if verified_claims.get("typ") != "Bearer":
        raise Denied("access_token_required")


def callback_host(headers, port: int) -> None:
    if headers.get_all("Host") != [f"127.0.0.1:{port}"]:
        raise Denied("invalid_callback_host")


@dataclass(frozen=True, repr=False)
class Trust:
    issuer: str
    keys: dict[str, Any]

    @classmethod
    def load(cls, http: Http) -> Trust:
        issuer = http.origin + "/realms/" + REALM
        metadata = http.request(issuer + "/.well-known/openid-configuration")
        expected = {
            "issuer": issuer,
            "jwks_uri": issuer + "/protocol/openid-connect/certs",
            "token_endpoint": issuer + "/protocol/openid-connect/token",
            "authorization_endpoint": issuer + "/protocol/openid-connect/auth",
        }
        if any(metadata.get(k) != v for k, v in expected.items()):
            raise Denied("discovery_mismatch")
        document = http.request(expected["jwks_uri"])
        keys = {}
        for raw in document.get("keys", []):
            if raw.get("use") != "sig" or raw.get("kty") != "RSA" or raw.get("alg") != "RS256":
                continue
            kid = raw.get("kid")
            if not isinstance(kid, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", kid):
                raise Denied("invalid_key_id")
            if kid in keys or any(k in raw for k in ("d", "p", "q", "dp", "dq", "qi", "oth")):
                raise Denied("untrusted_key_material")
            if "key_ops" in raw and raw["key_ops"] != ["verify"]:
                raise Denied("invalid_key_operations")
            try:
                key = jwt.PyJWK.from_dict(raw, algorithm="RS256").key
                if key.key_size < 2048:
                    raise Denied("weak_key")
            except (ValueError, jwt.PyJWTError):
                raise Denied("invalid_key") from None
            keys[kid] = key
        if not keys:
            raise Denied("signing_keys_missing")
        # Fresh trust per explicit verification run; no token-selected URL/refresh.
        return cls(issuer, keys)

    def decode(self, token: str, audience: str, *, required: list[str]) -> dict:
        try:
            if not isinstance(token, str) or len(token) > 16384 or token.count(".") != 2:
                raise Denied("invalid_token_shape")
            for segment in token.split(".")[:2]:
                json.loads(jwt.utils.base64url_decode(segment), object_pairs_hook=unique_object)
            header = jwt.get_unverified_header(token)
            if header.get("alg") != "RS256":
                raise Denied("algorithm_not_allowed")
            if header.get("typ") not in {"JWT", "at+jwt"}:
                raise Denied("header_type_not_allowed")
            if any(name in header for name in ("jku", "x5u", "jwk", "crit")):
                raise Denied("token_key_source_not_allowed")
            key = self.keys.get(header.get("kid"))
            if key is None:
                raise Denied("unknown_key_id")
            claims = jwt.decode(
                token, key, algorithms=["RS256"], issuer=self.issuer,
                audience=audience, leeway=0,
                options={"require": required},
            )
            if type(claims["iat"]) is not int or type(claims["exp"]) is not int:
                raise Denied("invalid_token_time")
            if "nbf" in claims and type(claims["nbf"]) is not int:
                raise Denied("invalid_token_time")
            if claims["exp"] <= claims["iat"] or claims["exp"] - claims["iat"] > 300:
                raise Denied("token_lifetime_not_allowed")
            if not isinstance(claims["sub"], str) or not claims["sub"]:
                raise Denied("subject_missing")
            return claims
        except jwt.ExpiredSignatureError:
            raise Denied("token_expired") from None
        except jwt.InvalidAudienceError:
            raise Denied("audience_mismatch") from None
        except jwt.InvalidIssuerError:
            raise Denied("issuer_mismatch") from None
        except (jwt.PyJWTError, ValueError, TypeError, KeyError):
            raise Denied("token_invalid") from None

    def access(self, token: str, audience: str, policy: dict) -> dict:
        claims = self.decode(token, audience, required=["iss", "sub", "aud", "exp", "iat", "typ"])
        # Keycloak-specific access profile: verified signed typ=Bearer, not RFC 9068 assumed.
        require_access_purpose(claims)
        if not isinstance(claims.get("jti"), str) or not claims["jti"] or "azp" not in claims:
            raise Denied("token_invalid")
        audiences = claims["aud"] if isinstance(claims["aud"], list) else [claims["aud"]]
        if set(audiences) != {audience}:
            raise Denied("excess_audience")
        if not isinstance(claims["azp"], str):
            raise Denied("workload_unknown")
        binding = policy["workloads"].get(claims["azp"])
        if binding is None:
            raise Denied("workload_unknown")
        if binding["subject"] != claims["sub"] or binding["audience"] != audience:
            raise Denied("workload_binding_mismatch")
        return binding

    def identity(self, token: str, nonce: str, policy: dict) -> dict:
        claims = self.decode(token, WEB, required=["iss", "sub", "aud", "exp", "iat", "nonce"])
        if (claims.get("typ") != "ID" or not isinstance(claims["nonce"], str)
                or not claims["nonce"].isascii() or not hmac.compare_digest(claims["nonce"], nonce)):
            raise Denied("id_token_binding_mismatch")
        if claims.get("azp", WEB) != WEB:
            raise Denied("id_token_client_mismatch")
        binding = policy["humans"].get(claims["sub"])
        if binding is None:
            raise Denied("human_unknown")
        return binding


def authorize(binding: dict, organization: str | None, permissions: list[str]) -> dict:
    memberships = binding["memberships"]
    if organization is None:
        if len(memberships) != 1:
            raise Denied("organization_selection_required")
        organization = next(iter(memberships))
    if organization not in memberships:
        raise Denied("organization_not_authorized")
    granted = memberships[organization]
    if not set(permissions).issubset(granted):
        raise Denied("permission_not_granted")
    return {"principal": binding["principal"], "organization": organization, "permissions": sorted(granted)}


def pkce_transaction(issuer: str, redirect: str) -> dict:
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return {"state": secrets.token_urlsafe(32), "nonce": secrets.token_urlsafe(32),
            "verifier": verifier, "challenge": challenge, "issuer": issuer,
            "redirect": redirect, "deadline": time.monotonic() + 300}


def callback_code(raw_path: str, transaction: dict) -> str:
    if time.monotonic() >= transaction["deadline"] or transaction.get("used"):
        raise Denied("callback_expired_or_used")
    parsed = urllib.parse.urlsplit(raw_path)
    if parsed.scheme or parsed.netloc or parsed.fragment or parsed.path != "/callback" or len(raw_path) > 8192:
        raise Denied("invalid_callback")
    pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    values = dict(pairs)
    if len(values) != len(pairs) or set(values) - {"state", "code", "session_state", "iss"}:
        raise Denied("invalid_callback_fields")
    if not values.get("state", "").isascii() or not hmac.compare_digest(values.get("state", ""), transaction["state"]):
        raise Denied("callback_state_mismatch")
    if values.get("iss") != transaction["issuer"] or not values.get("code"):
        raise Denied("callback_issuer_or_code_mismatch")
    transaction["used"] = True
    return values["code"]
