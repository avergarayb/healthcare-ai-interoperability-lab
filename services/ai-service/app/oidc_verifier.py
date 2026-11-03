"""Resource-server cryptography and bounded provider/issuer-scoped key cache."""
from __future__ import annotations

import json
import re
import threading
import time
import logging
from contextvars import ContextVar
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx
import jwt

from app.oidc_config import Rejected, TrustConfig, unique_object


@dataclass(frozen=True, repr=False)
class VerifiedWorkload:
    subject: str
    client_id: str
    expires_at: int


def keycloak_workload_profile(claims):
    if claims.get("typ") != "Bearer":
        raise Rejected("purpose_rejected")
    if (not isinstance(claims["sub"], str) or not 1 <= len(claims["sub"]) <= 512
            or not isinstance(claims.get("jti"), str) or not 1 <= len(claims["jti"]) <= 256
            or not isinstance(claims.get("azp"), str) or not 1 <= len(claims["azp"]) <= 128):
        raise Rejected("verification_rejected")
    return VerifiedWorkload(claims["sub"], claims["azp"], claims["exp"])


PROFILES = {"keycloak-client-credentials-v1": keycloak_workload_profile}


_METADATA_IO = ContextVar("oidc_metadata_io", default=False)


class _MetadataLogFilter(logging.Filter):
    def filter(self, record):
        return not _METADATA_IO.get()


# Suppress only this boundary's SDK traffic logs, including issuer URLs. Other
# HTTP clients retain their existing logging policy, also on concurrent threads.
for _logger_name in ("httpx", "httpcore.connection", "httpcore.http11", "httpcore.http2",
                     "httpcore.proxy", "httpcore.http_proxy", "httpcore.socks_proxy"):
    logging.getLogger(_logger_name).addFilter(_MetadataLogFilter())


class MetadataClient:
    def __init__(self, config: TrustConfig):
        self.config = config

    def get(self, url: str) -> dict:
        scope = _METADATA_IO.set(True)
        try:
            return self._get(url)
        finally:
            _METADATA_IO.reset(scope)

    def _get(self, url: str) -> dict:
        config = self.config
        if url not in (config.discovery_url, config.expected_jwks_uri):
            raise Rejected("discovery_mismatch", 503)
        try:
            transport = None
            if config.allow_http_loopback and urlsplit(url).scheme == "http" and urlsplit(url).hostname == "localhost":
                # Bind the explicit local HTTP exception to IPv4. Keep the URI,
                # Host header and issuer unchanged; no dynamic aliases or TLS bypass.
                transport = httpx.HTTPTransport(local_address="127.0.0.1", trust_env=False, verify=True)
            with httpx.Client(transport=transport, timeout=config.http_timeout_seconds, trust_env=False, follow_redirects=False) as client:
                # The network budget starts after local TLS/client construction.
                deadline = time.monotonic() + config.http_timeout_seconds
                with client.stream("GET", url, headers={"Accept": "application/json", "Accept-Encoding": "identity"}) as response:
                    if response.status_code != 200:
                        raise Rejected("provider_unavailable", 503)
                    if response.headers.get("content-encoding", "identity").lower() != "identity":
                        raise Rejected("provider_unavailable", 503)
                    raw = bytearray()
                    for chunk in response.iter_bytes():
                        raw.extend(chunk)
                        if len(raw) > config.metadata_max_bytes or time.monotonic() > deadline:
                            raise Rejected("provider_unavailable", 503)
            value = json.loads(raw, object_pairs_hook=unique_object)
            if not isinstance(value, dict):
                raise ValueError("invalid response")
            return value
        except (httpx.HTTPError, OSError):
            raise Rejected("provider_unavailable", 503) from None
        except (ValueError, TypeError):
            raise Rejected("discovery_mismatch", 503) from None


class KeyCache:
    def __init__(self, config: TrustConfig, fetch=None, monotonic=time.monotonic):
        self.config, self.fetch, self.clock = config, fetch or MetadataClient(config).get, monotonic
        self._keys, self._loaded, self._attempt = {}, None, float("-inf")
        self._lock = threading.Lock()

    def _refresh(self):
        config = self.config
        metadata = self.fetch(config.discovery_url)
        if metadata.get("issuer") != config.issuer or metadata.get("jwks_uri") != config.expected_jwks_uri:
            raise Rejected("discovery_mismatch", 503)
        for name in ("authorization_endpoint", "token_endpoint"):
            if metadata.get(name) not in config.endpoint_allowlist:
                raise Rejected("discovery_mismatch", 503)
        document = self.fetch(config.expected_jwks_uri)
        values = document.get("keys")
        if not isinstance(values, list) or not 1 <= len(values) <= 32:
            raise Rejected("keys_invalid", 503)
        keys = {}
        for raw in values:
            if not isinstance(raw, dict) or any(k in raw for k in ("d", "p", "q", "dp", "dq", "qi", "oth")):
                raise Rejected("keys_invalid", 503)
            if raw.get("use") != "sig" or raw.get("kty") != "RSA" or raw.get("alg") != "RS256":
                continue
            kid = raw.get("kid")
            if (not isinstance(kid, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", kid)
                    or kid in keys or ("key_ops" in raw and raw["key_ops"] != ["verify"])
                    or not isinstance(raw.get("n"), str) or len(raw["n"]) > 1400):
                raise Rejected("keys_invalid", 503)
            try:
                key = jwt.PyJWK.from_dict(raw, algorithm="RS256").key
                if not 2048 <= key.key_size <= 8192:
                    raise ValueError("invalid strength")
            except (ValueError, TypeError, KeyError, jwt.PyJWTError):
                raise Rejected("keys_invalid", 503) from None
            keys[kid] = key
        if not keys:
            raise Rejected("keys_invalid", 503)
        self._keys, self._loaded = keys, self.clock()

    def key(self, kid: str):
        with self._lock:
            now = self.clock()
            hard_expired = self._loaded is None or now - self._loaded >= self.config.jwks_hard_ttl_seconds
            needs_refresh = (hard_expired or kid not in self._keys
                             or now - self._loaded >= self.config.jwks_refresh_seconds)
            if needs_refresh and now - self._attempt >= self.config.unknown_kid_refresh_min_interval_seconds:
                self._attempt = now
                try:
                    self._refresh()
                except Rejected as error:
                    if error.reason != "provider_unavailable":
                        self._keys, self._loaded = {}, None
                    if hard_expired or kid not in self._keys or error.reason != "provider_unavailable":
                        raise
            if self._loaded is None or self.clock() - self._loaded >= self.config.jwks_hard_ttl_seconds:
                raise Rejected("keys_unavailable", 503)
            if kid not in self._keys:
                raise Rejected("unknown_key", 401)
            return self._keys[kid]


class AccessVerifier:
    def __init__(self, config: TrustConfig, cache=None, clock=time.time):
        self.config, self.cache, self.clock = config, cache or KeyCache(config), clock

    def verify(self, token: str) -> VerifiedWorkload:
        config = self.config
        if not config.enabled:
            raise Rejected("provider_disabled", 503)
        try:
            if len(token) > 16384 or not re.fullmatch(r"[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", token):
                raise Rejected("credential_malformed")
            for part in token.split(".")[:2]:
                value = json.loads(jwt.utils.base64url_decode(part), object_pairs_hook=unique_object)
                if not isinstance(value, dict):
                    raise ValueError("invalid claims")
            header = jwt.get_unverified_header(token)
            if header.get("alg") not in config.allowed_algorithms or header.get("typ") not in {"JWT", "at+jwt"}:
                raise Rejected("algorithm_rejected")
            if any(k in header for k in ("jku", "x5u", "jwk", "x5c", "crit")):
                raise Rejected("key_source_rejected")
            kid = header.get("kid")
            if not isinstance(kid, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", kid):
                raise Rejected("unknown_key")
            key = self.cache.key(kid)
            claims = jwt.decode(token, key, algorithms=list(config.allowed_algorithms), issuer=config.issuer,
                                audience=list(config.accepted_audiences), leeway=config.clock_skew_seconds,
                                options={"require": ["iss", "sub", "aud", "iat", "exp"]})
            now = self.clock()
            if any(type(claims[k]) is not int for k in ("iat", "exp")) or ("nbf" in claims and type(claims["nbf"]) is not int):
                raise Rejected("time_rejected")
            if claims["exp"] <= now:
                raise Rejected("token_expired")
            if (claims["iat"] > now + config.clock_skew_seconds
                    or not 0 < claims["exp"] - claims["iat"] <= config.max_access_token_lifetime_seconds):
                raise Rejected("time_rejected")
            aud = claims["aud"] if isinstance(claims["aud"], list) else [claims["aud"]]
            if len(aud) != 1 or set(aud) != set(config.accepted_audiences):
                raise Rejected("audience_rejected")
            return PROFILES[config.access_token_profile](claims)
        except jwt.ExpiredSignatureError:
            raise Rejected("token_expired") from None
        except jwt.ImmatureSignatureError:
            raise Rejected("time_rejected") from None
        except jwt.InvalidAudienceError:
            raise Rejected("audience_rejected") from None
        except jwt.InvalidIssuerError:
            raise Rejected("provider_untrusted") from None
        except (jwt.PyJWTError, ValueError, TypeError, KeyError):
            raise Rejected("verification_rejected") from None
