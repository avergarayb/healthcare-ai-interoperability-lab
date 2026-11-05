"""Immutable internal contracts. None is an incoming credential or wire API."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Protocol


class ConnectorOperation(str, Enum):
    RESOLVE = "resource.resolve_registered"
    METADATA = "resource.metadata.read"
    CHILDREN = "resource.children.list"
    READ = "document.content.read"
    PROVENANCE = "resource.provenance.read"
    AI_PROCESS = "document.model.process"
    INDEX = "document.index"
    SHARE = "document.share"


class Gate(str, Enum):
    READ = "A"
    DELIVERY = "B"
    AI_PROCESS = "C"
    INDEX = "D"


class Outcome(str, Enum):
    LOCAL_ALLOW = "LOCAL_ALLOW"
    DENY = "DENY"
    UNAVAILABLE = "UNAVAILABLE"
    EXTERNAL_SUCCESS = "EXTERNAL_SUCCESS"
    EXTERNAL_DENIED = "EXTERNAL_DENIED"
    DELIVERY_ALLOWED = "DELIVERY_ALLOWED"
    DELIVERY_SUPPRESSED = "DELIVERY_SUPPRESSED"


class Reason(str, Enum):
    ALLOWED = "access_granted"
    IDENTITY = "principal_invalid"
    PRINCIPAL_TYPE = "principal_type_rejected"
    EXPIRED = "context_expired"
    ORGANIZATION = "organization_mismatch"
    NOT_REGISTERED = "connector_not_registered"
    OPERATION = "operation_unsupported"
    RESOURCE = "resource_out_of_scope"
    GRANT = "permission_revoked"
    BINDING = "tenant_binding_mismatch"
    MODE = "mode_rejected"
    CREDENTIAL = "credential_unavailable"
    CREDENTIAL_EXPIRED = "credential_expired"
    DATA_USE = "data_use_denied"
    STALE = "policy_revision_changed"
    LIMIT = "execution_limit_exceeded"
    AUDIT = "audit_unavailable"
    POLICY = "connector_policy_error"
    EXTERNAL = "external_access_denied"
    MISSING = "external_resource_missing"
    PROVIDER = "external_provider_unavailable"
    TRANSPORT = "transport_rejected"
    CONTENT = "content_rejected"
    REPLAY = "decision_rejected"
    CHANGE = "synthetic_policy_change"


class Phase(str, Enum):
    AUTHORIZATION = "local_authorization"
    EXTERNAL = "external_execution"
    DELIVERY = "delivery"
    CHANGE = "grant_administration"


@dataclass(frozen=True, slots=True)
class ExecutionLimits:
    max_pages: int = 3
    max_items: int = 8
    max_bytes: int = 1024
    max_attempts: int = 3
    max_seconds: int = 5
    max_concurrent: int = 2


@dataclass(frozen=True, slots=True)
class ConnectorDefinition:
    definition_id: str
    operations: frozenset[ConnectorOperation]
    enabled: bool = True
    version: int = 1
    allowed_mimes: frozenset[str] = frozenset({"text/plain"})
    limits: ExecutionLimits = ExecutionLimits()


@dataclass(frozen=True, slots=True)
class ConnectorInstance:
    instance_id: str
    organization_id: str
    definition_id: str
    binding_id: str
    credential_ref: str
    mode: str = "application"
    enabled: bool = True
    lifecycle_status: str = "active"
    version: int = 1


@dataclass(frozen=True, slots=True)
class TenantConnectorBinding:
    binding_id: str
    organization_id: str
    instance_id: str
    tenant_id: str
    client_id: str
    service_principal_id: str
    provider: str = "synthetic-documents"
    cloud: str = "synthetic"
    mode: str = "application"
    enabled: bool = True
    version: int = 1


@dataclass(frozen=True, slots=True)
class QualifiedExternalResource:
    resource_id: str
    organization_id: str
    instance_id: str
    tenant_id: str
    external_id: str
    parent_id: str | None = None
    provider: str = "synthetic-documents"
    cloud: str = "synthetic"
    resource_type: str = "document"
    classification: str = "synthetic-internal"
    kind: str = "registered"
    enabled: bool = True
    version: int = 1


@dataclass(frozen=True, slots=True)
class ExternalResourceGrant:
    grant_id: str
    organization_id: str
    instance_id: str
    resource_id: str
    operations: frozenset[ConnectorOperation]
    expires_at: datetime
    scope: str = "exact"
    mode: str = "application"
    profile: str = "synthetic-selected-read"
    enabled: bool = True
    version: int = 1


@dataclass(frozen=True, slots=True)
class ConnectorPrincipalGrant:
    grant_id: str
    principal_id: str
    organization_id: str
    instance_id: str
    resource_id: str
    operations: frozenset[ConnectorOperation]
    expires_at: datetime
    gates: frozenset[Gate] = frozenset({Gate.READ, Gate.DELIVERY})
    purposes: frozenset[str] = frozenset({"synthetic-demonstration"})
    recipients: frozenset[str] = frozenset()
    classifications: frozenset[str] = frozenset({"synthetic-internal"})
    scope: str = "exact"
    mode: str = "application"
    enabled: bool = True
    version: int = 1


@dataclass(frozen=True, slots=True, repr=False)
class CredentialReference:
    reference_id: str
    organization_id: str
    instance_id: str
    tenant_id: str
    client_id: str
    service_principal_id: str
    expires_at: datetime
    provider: str = "synthetic-documents"
    cloud: str = "synthetic"
    mode: str = "application"
    profile: str = "synthetic-selected-read"
    enabled: bool = True
    version: int = 1


@dataclass(frozen=True, slots=True, repr=False)
class ConnectorExecutionContext:
    """Test boundary's verified-context analogue, never deserialized from input."""
    principal_id: str
    organization_id: str
    authenticated_at: datetime
    expires_at: datetime
    principal_type: str = "workload"
    audience: str = "healthcare-ai-api"
    context_version: str = "identity-principal-context-v1"


class IdentityBoundary(Protocol):
    def recognizes(self, context: ConnectorExecutionContext) -> bool: ...


@dataclass(frozen=True, slots=True)
class RegisteredPrincipal:
    principal_id: str
    organization_id: str
    principal_type: str = "workload"
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class OperationRequest:
    instance_id: str
    resource_id: str
    operation: ConnectorOperation
    purpose: str
    recipient_id: str
    policy_version: int


@dataclass(frozen=True, slots=True)
class ConnectorAccessDecision:
    decision_id: str
    correlation_id: str
    context: ConnectorExecutionContext = field(repr=False)
    request: OperationRequest
    policy_revision: int
    expires_at: datetime
    gate: Gate


@dataclass(frozen=True, slots=True)
class ConnectorAuditEvent:
    event_id: str
    correlation_id: str
    timestamp: datetime
    phase: Phase
    outcome: Outcome
    reason: Reason
    policy_revision: int
    principal_id: str | None = None
    organization_id: str | None = None
    instance_id: str | None = None
    resource_id: str | None = None
    operation: ConnectorOperation | None = None
    contract_version: str = "connector-security-audit-v1"


@dataclass(frozen=True, slots=True)
class UntrustedDocument:
    resource_id: str
    organization_id: str
    instance_id: str
    version: int
    text: str = field(repr=False)
    label: str = "untrusted_enterprise_document"


@dataclass(frozen=True, slots=True)
class OperationResult:
    status: Outcome
    reason: Reason
    correlation_id: str
    local_status: Outcome
    external_status: Outcome | None = None
    delivery_status: Outcome | None = None
    documents: tuple[UntrustedDocument, ...] = field(default=(), repr=False)


class ConnectorFailure(Exception):
    def __init__(self, reason: Reason, *, unavailable: bool = False):
        self.reason, self.unavailable = reason, unavailable
        super().__init__(reason.value)
