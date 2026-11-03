"""Opt-in technical identity projection; no clinical, graph or model imports."""
from __future__ import annotations

import re
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import time

from fastapi import Request
from fastapi.responses import JSONResponse

from app.oidc_config import AUDIENCE, ID, PERMISSION, ROUTE, Rejected, load_config
from app.oidc_verifier import AccessVerifier
from app.oidc_workload_audit import WorkloadAudit
from app.trusted_identity_registry import RegistryError, TrustedIdentityRegistry


@dataclass(frozen=True, repr=False)
class PrincipalContext:
    internal_principal_id: str
    organization_id: str
    provider_id: str
    external_issuer: str
    external_subject: str
    effective_permissions: tuple[str, ...]
    authenticated_at: str
    expires_at: str
    correlation_id: str
    context_version: str = "identity-principal-context-v1"
    principal_type: str = "workload"
    authentication_method: str = "oauth2_client_credentials"
    audience: str = AUDIENCE

    def projection(self):
        return {k: v for k, v in asdict(self).items() if k not in {"external_issuer", "external_subject", "provider_id"}}


def instant(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat().replace("+00:00", "Z")


def correlation_for(request):
    values = request.headers.getlist("X-Correlation-ID")
    if len(values) == 1:
        try:
            parsed = uuid.UUID(values[0])
            if parsed.version == 4 and str(parsed) == values[0]:
                return values[0]
        except ValueError:
            pass
    return str(uuid.uuid4())


def credential(request):
    if request.headers.getlist("X-Service-Token") or request.headers.getlist("Cookie"):
        raise Rejected("credential_conflict")
    values = request.headers.getlist("Authorization")
    if not values:
        raise Rejected("credential_missing")
    if len(values) != 1:
        raise Rejected("credential_ambiguous")
    value = values[0]
    if len(value) > 16391 or not re.fullmatch(r"Bearer [A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", value):
        raise Rejected("credential_malformed")
    return value[7:]


def organization_for(request):
    values = request.headers.getlist("X-IAM-Lab-Organization")
    if not values:
        return None
    if len(values) != 1 or not ID.fullmatch(values[0]):
        raise Rejected("organization_rejected", 403)
    return values[0]


class WorkloadBoundary:
    def __init__(self, config_path, audit_path, forbidden_paths=(), *, policy_mode="static", registry_path=""):
        self.config = self.verifier = self.audit = None
        self.policy_mode, self.registry = policy_mode, None
        if policy_mode == "sqlite":
            try:
                self.registry = TrustedIdentityRegistry(registry_path, (*forbidden_paths, audit_path))
            except (RegistryError, OSError, ValueError):
                pass
        try:
            audit_forbidden = (*forbidden_paths, registry_path) if policy_mode == "sqlite" else forbidden_paths
            if not audit_path or Path(audit_path).resolve() in {Path(p).resolve() for p in audit_forbidden if p}:
                raise ValueError("separate audit store required")
            self.audit = WorkloadAudit(audit_path)
        except (ValueError, OSError):
            pass
        try:
            self.config = load_config(config_path)
            self.verifier = AccessVerifier(self.config)
        except Rejected:
            pass

    def context(self, token, correlation, candidate=None, *, request=None):
        if self.config is None or self.verifier is None:
            raise Rejected("configuration_incomplete", 503)
        config = self.config
        verified = self.verifier.verify(token)
        if request is not None:
            candidate = organization_for(request)
        if self.policy_mode == "sqlite":
            if self.registry is None:
                raise Rejected("registry_unavailable", 503)
            policy = self.registry.resolve(config, verified, candidate)
            now = time()
            if now >= verified.expires_at:
                raise Rejected("token_expired")
            return PrincipalContext(policy.principal_id, policy.organization_id, config.provider_id,
                                    config.issuer, verified.subject, policy.permissions,
                                    instant(now), instant(verified.expires_at), correlation)
        if self.policy_mode != "static":
            raise Rejected("configuration_incomplete", 503)
        binding = next((b for b in config.bindings if b.client_id == verified.client_id and b.external_subject == verified.subject), None)
        if binding is None:
            raise Rejected("binding_unknown")
        if not binding.binding_enabled:
            raise Rejected("binding_disabled", 403)
        if not binding.principal_enabled:
            raise Rejected("principal_disabled", 403)
        if not binding.membership_enabled or binding.organization_id not in config.allowed_organization_ids:
            raise Rejected("organization_rejected", 403)
        if candidate is not None and candidate != binding.organization_id:
            raise Rejected("organization_rejected", 403)
        if PERMISSION not in binding.permissions:
            raise Rejected("policy_rejected", 403)
        now = time()
        if now >= verified.expires_at:
            raise Rejected("token_expired")
        return PrincipalContext(binding.internal_principal_id, binding.organization_id, config.provider_id,
                                config.issuer, verified.subject, (PERMISSION,),
                                instant(now), instant(verified.expires_at), correlation)

    def handle(self, request):
        correlation = correlation_for(request)
        context, status, reason = None, 200, "access_granted"
        try:
            token = credential(request)
            # Crypto precedes policy; this bounded candidate never proves membership.
            context = self.context(token, correlation, request=request)
        except Rejected as error:
            status, reason = error.status, error.reason
        # Only fixed server codes and trusted registration ids reach the audit.
        try:
            if self.audit is None:
                raise Rejected("audit_unavailable", 503)
            self.audit.append(reason=reason, correlation=correlation,
                              provider=None if self.config is None else self.config.provider_id, context=context)
        except Rejected:
            status, context = 503, None
        # A successful audit append cannot extend the credential's lifetime.
        if context is not None and time() >= datetime.fromisoformat(context.expires_at.replace("Z", "+00:00")).timestamp():
            status, context = 401, None
        headers = {"Cache-Control": "no-store", "X-Correlation-ID": correlation}
        if status == 200:
            return JSONResponse(context.projection(), headers=headers)
        if status == 401:
            headers["WWW-Authenticate"] = "Bearer"
        return JSONResponse({"error": {401: "unauthorized", 403: "forbidden", 503: "unavailable"}[status]}, status_code=status, headers=headers)


def configure_boundary(application, settings):
    # A new lifespan may be used by a test host. Never leave an old enabled route.
    application.router.routes[:] = [r for r in application.router.routes if getattr(r, "name", None) != "oidc_workload_context_v1"]
    application.openapi_schema = None
    if not settings.oidc_workload_lab_enabled:
        return
    legacy_audit = settings.security_audit_db_path or str(Path(settings.human_session_db_path).parent / "security-audit.sqlite3")
    boundary = WorkloadBoundary(settings.oidc_workload_trust_config_path, settings.oidc_workload_audit_db_path,
                                (settings.ai_review_db_path, settings.human_session_db_path,
                                 settings.institutional_knowledge_db_path, legacy_audit,
                                 str(Path(settings.ai_review_db_path).resolve().parent / "agent-workflow.sqlite3")),
                                policy_mode=settings.oidc_workload_policy_mode,
                                registry_path=settings.oidc_workload_registry_db_path)
    def endpoint(request: Request):
        return boundary.handle(request)
    application.add_api_route(ROUTE, endpoint, methods=["GET"], name="oidc_workload_context_v1")
