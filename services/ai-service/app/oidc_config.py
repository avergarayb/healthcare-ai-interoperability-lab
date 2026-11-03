"""Operator-owned OIDC registration. No token-selected providers or endpoints."""
from __future__ import annotations

import ipaddress
import json
import re
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, model_validator

AUDIENCE = "healthcare-ai-api"
PERMISSION = "iam.workload-context.read"
ROUTE = "/iam-lab/v1/workload-context"
ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9.-]{0,63}\Z")


class Rejected(Exception):
    def __init__(self, reason: str, status: int = 401):
        self.reason, self.status = reason, status
        super().__init__(reason)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate field")
        result[key] = value
    return result


class Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, hide_input_in_errors=True)


class WorkloadBinding(Closed):
    client_id: str = Field(min_length=1, max_length=128)
    external_subject: str = Field(min_length=1, max_length=512)
    internal_principal_id: str
    principal_type: Literal["workload"]
    binding_enabled: bool
    principal_enabled: bool
    organization_id: str
    membership_enabled: bool
    audience: Literal["healthcare-ai-api"]
    permissions: tuple[str, ...]

    @model_validator(mode="after")
    def bounded(self):
        if not ID.fullmatch(self.internal_principal_id) or not ID.fullmatch(self.organization_id):
            raise ValueError("invalid registered id")
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", self.client_id):
            raise ValueError("invalid client")
        if any(ord(c) < 33 for c in self.external_subject):
            raise ValueError("invalid subject")
        if len(self.permissions) > 16 or len(set(self.permissions)) != len(self.permissions):
            raise ValueError("invalid permissions")
        if any(not re.fullmatch(r"[a-z][a-z0-9.-]{0,79}", p) for p in self.permissions):
            raise ValueError("invalid permission")
        return self


class TrustConfig(Closed):
    contract_version: Literal["python-oidc-workload-v1"]
    provider_id: str
    enabled: bool
    issuer: str
    discovery_url: str
    expected_jwks_uri: str
    endpoint_allowlist: tuple[str, ...]
    accepted_audiences: tuple[Literal["healthcare-ai-api"], ...]
    allowed_algorithms: tuple[Literal["RS256"], ...]
    access_token_profile: Literal["keycloak-client-credentials-v1"]
    allow_http_loopback: bool
    allowed_organization_ids: tuple[str, ...]
    clock_skew_seconds: int = Field(ge=0, le=60)
    max_access_token_lifetime_seconds: int = Field(ge=1, le=300)
    jwks_refresh_seconds: int = Field(ge=30, le=300)
    jwks_hard_ttl_seconds: int = Field(ge=30, le=900)
    unknown_kid_refresh_min_interval_seconds: int = Field(ge=30, le=300)
    http_timeout_seconds: float = Field(gt=0, le=2)
    metadata_max_bytes: int = Field(ge=1024, le=1048576)
    bindings: tuple[WorkloadBinding, ...]

    @model_validator(mode="after")
    def trusted(self):
        if not ID.fullmatch(self.provider_id):
            raise ValueError("invalid provider id")
        if self.accepted_audiences != (AUDIENCE,) or self.allowed_algorithms != ("RS256",):
            raise ValueError("unsupported resource profile")
        if not 1 <= len(self.allowed_organization_ids) <= 32 or any(not ID.fullmatch(v) for v in self.allowed_organization_ids):
            raise ValueError("invalid organization registration")
        if self.jwks_refresh_seconds > self.jwks_hard_ttl_seconds:
            raise ValueError("invalid cache policy")
        urls = (self.issuer, self.discovery_url, self.expected_jwks_uri, *self.endpoint_allowlist)
        if len(urls) > 12:
            raise ValueError("too many endpoints")
        for url in urls:
            parsed = urlsplit(url)
            if (len(url) > 2048 or parsed.username or parsed.password or parsed.query or parsed.fragment
                    or not parsed.hostname or parsed.scheme not in {"http", "https"}
                    or any(ord(c) < 33 for c in url)):
                raise ValueError("invalid trusted URL")
            loopback = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
            if parsed.scheme == "http" and not (self.allow_http_loopback and loopback):
                raise ValueError("HTTP requires explicit loopback exception")
            try:
                address = ipaddress.ip_address(parsed.hostname)
            except ValueError:
                address = None
            if address and not address.is_global and not (self.allow_http_loopback and loopback):
                raise ValueError("unapproved IP endpoint")
            if loopback and not self.allow_http_loopback:
                raise ValueError("loopback exception required")
            if parsed.port is not None and not (1024 <= parsed.port <= 65535 or (parsed.scheme == "https" and parsed.port == 443)):
                raise ValueError("unapproved port")
        if not {self.discovery_url, self.expected_jwks_uri}.issubset(self.endpoint_allowlist):
            raise ValueError("endpoints not approved")
        if len(self.bindings) > 64 or len({b.client_id for b in self.bindings}) != len(self.bindings):
            raise ValueError("ambiguous bindings")
        if len({b.external_subject for b in self.bindings}) != len(self.bindings):
            raise ValueError("ambiguous external identity")
        return self


def load_config(path: str) -> TrustConfig:
    try:
        with Path(path).open("rb") as stream:
            data = stream.read(65537)
        if len(data) > 65536:
            raise ValueError("configuration too large")
        value = json.loads(data, object_pairs_hook=unique_object)
        return TrustConfig.model_validate_json(json.dumps(value))
    except (OSError, ValueError, TypeError):
        raise Rejected("configuration_incomplete", 503) from None
