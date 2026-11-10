"""Internal C01 records, not deserializers, credentials or execution capabilities."""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Protocol

from ..enterprise_connectors.models import ConnectorExecutionContext, ConnectorOperation, OperationRequest
from ..enterprise_connectors.registry import PolicySnapshot


PROFILE_ID = "fake-enterprise-extractive-v1"
DESTINATION = "in-process-offline"
PROCESSING_OPERATION = "enterprise.document.answer"
PROCESSING_PURPOSE = "synthetic-policy-question-answering"
CLASSIFICATION = "synthetic-internal"
RETENTION = "ephemeral-no-retention"
QUESTION = "¿Cuántos días de vacaciones establece la política?"


class ProcessingOutcome(str, Enum):
    ALLOW_PROCESSING = "ALLOW_PROCESSING"
    DENY = "DENY"
    UNAVAILABLE = "UNAVAILABLE"


class ProcessingReason(str, Enum):
    ALLOWED = "processing_eligible_not_executable"
    INPUT = "invalid_input"
    IDENTITY = "identity_invalid"
    SCOPE = "scope_mismatch"
    SOURCE = "source_evidence_invalid"
    GRANT = "processing_not_granted"
    PROFILE = "profile_denied"
    CLASSIFICATION = "classification_denied"
    PURPOSE = "purpose_denied"
    RETENTION = "retention_unverified"
    APPROVAL = "approval_required"
    STALE = "policy_changed"
    EXPIRED = "authorization_expired"
    LIMIT = "budget_exceeded"
    UNVERIFIABLE = "authority_unverifiable"


@dataclass(frozen=True, slots=True)
class ProcessingLimits:
    max_sources: int = 1
    max_source_bytes: int = 1024
    max_question_bytes: int = 256
    max_input_bytes: int = 2048
    max_output_bytes: int = 512
    max_output_units: int = 256
    max_seconds: int = 5
    max_retries: int = 0
    max_concurrent: int = 1  # Declaration only; no reservation in C01.


@dataclass(frozen=True, slots=True, repr=False)
class AIProcessingEnvelope:
    operation_id: str
    context: ConnectorExecutionContext
    read_request: OperationRequest
    binding_id: str
    tenant_id: str
    source_ref: str
    registered_version: int
    content_revision: int
    connector_revision: int
    processing_revision: int
    profile_id: str
    profile_version: int
    issued_at: datetime
    expires_at: datetime
    question: str
    processing_operation: str = PROCESSING_OPERATION
    processing_purpose: str = PROCESSING_PURPOSE
    limits: ProcessingLimits = ProcessingLimits()


@dataclass(frozen=True, slots=True, repr=False)
class SourceEvidence:
    """Recognized test-owner receipt. Contains no text, digest or Graph eTag."""
    source_ref: str
    organization_id: str
    instance_id: str
    tenant_id: str
    resource_id: str
    registered_version: int
    content_revision: int
    classification: str
    provenance: str
    utf8_bytes: int
    read_correlation_id: str
    connector_revision: int
    observed_at: datetime


@dataclass(frozen=True, slots=True)
class ModelProcessingProfile:
    organization_id: str
    valid_from: datetime
    expires_at: datetime
    review_due_at: datetime
    profile_id: str = PROFILE_ID
    version: int = 1
    enabled: bool = True
    provider: str = "fake"
    model_id: str = PROFILE_ID
    model_version: str = "1"
    destination: str = DESTINATION
    classification: str = CLASSIFICATION
    processing_purpose: str = PROCESSING_PURPOSE
    retention: str = RETENTION
    tokenizer: str = "fake-byte-v1"  # Declarative identifier, no tokenizer here.
    questions: frozenset[str] = frozenset({QUESTION})
    limits: ProcessingLimits = ProcessingLimits()


@dataclass(frozen=True, slots=True)
class AIProcessingGrant:
    grant_id: str
    principal_id: str
    organization_id: str
    instance_id: str
    tenant_id: str
    resource_id: str
    recipient_id: str
    valid_from: datetime
    expires_at: datetime
    review_due_at: datetime
    approval: str  # Explicit synthetic exemption required; never inferred.
    principal_type: str = "workload"
    read_operation: ConnectorOperation = ConnectorOperation.READ
    read_purpose: str = "synthetic-demonstration"
    processing_operation: str = PROCESSING_OPERATION
    processing_purpose: str = PROCESSING_PURPOSE
    classification: str = CLASSIFICATION
    profile_id: str = PROFILE_ID
    profile_version: int = 1
    enabled: bool = True
    version: int = 1
    limits: ProcessingLimits = ProcessingLimits()


@dataclass(frozen=True, slots=True)
class AIProcessingPolicy:
    revision: int
    grants: tuple[AIProcessingGrant, ...]
    profiles: tuple[ModelProcessingProfile, ...]


class ProcessingBoundary(Protocol):
    """Trusted, side-effect-free composition port. Only TEST issuers exist.

    False means unrecognized. Errors/non-bools mean unavailable authority.
    This does not replace the connector's existing IdentityBoundary.
    """
    def recognizes_envelope(self, envelope: AIProcessingEnvelope) -> bool: ...
    def recognizes_source(self, evidence: SourceEvidence, envelope: AIProcessingEnvelope) -> bool: ...
    def recognizes_policy(self, connector: PolicySnapshot, processing: AIProcessingPolicy) -> bool: ...


@dataclass(frozen=True, slots=True)
class AIProcessingDecision:
    outcome: ProcessingOutcome
    reason: ProcessingReason
    operation_id: str | None = None
    organization_id: str | None = None
    resource_id: str | None = None
    connector_revision: int | None = None
    processing_revision: int | None = None
    expires_at: datetime | None = None
