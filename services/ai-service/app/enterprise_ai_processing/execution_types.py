"""C02 domain records and ports. No SQL, provider settings or identity issuer."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol
from types import MappingProxyType
from uuid import UUID

from ..enterprise_connectors.registry import SAFE_ID
from .models import AIProcessingEnvelope, SourceEvidence


REASONS = frozenset({"processing_eligible_not_executable", "invalid_input", "identity_invalid", "scope_mismatch",
    "source_evidence_invalid", "processing_not_granted", "classification_denied", "purpose_denied", "profile_denied",
    "destination_denied", "retention_unverified", "approval_required", "policy_changed", "authorization_expired",
    "budget_exceeded", "authority_unverifiable", "provider_unavailable", "provider_result_invalid", "audit_unavailable",
    "cancelled", "internal_failure", "accepted", "lease_invalid", "execution_unknown", "deadline_exceeded", "revision_conflict"})
TERMINAL = frozenset({"COMPLETED", "INVALID", "FAILED", "CANCELLED", "TIMED_OUT", "REVOKED", "EXPIRED", "UNKNOWN"})
EVENTS = MappingProxyType({
    "ai_processing_evaluated": ("evaluation", frozenset({"ALLOW", "DENY", "UNAVAILABLE"})),
    "ai_processing_profile_selected": ("preparation", frozenset({"ALLOW"})),
    "ai_processing_budget_approved": ("preparation", frozenset({"ALLOW"})),
    "ai_processing_authorized": ("preparation", frozenset({"AUTHORIZED"})),
    "ai_provider_invocation_observed": ("entry", frozenset({"OBSERVED"})),
    "ai_provider_result_observed": ("result", frozenset({"OBSERVED", "UNKNOWN"})),
    "ai_processing_cancelled": ("cleanup", frozenset({"CANCELLED"})),
    "ai_processing_error": ("cleanup", frozenset({"ERROR", "UNKNOWN"})),
    "ai_processing_revocation_detected": ("cleanup", frozenset({"REVOKED"})),
    "ai_processing_policy_changed": ("administration", frozenset({"CHANGED"})),
})


class ExecutionError(Exception):
    def __init__(self, reason="authority_unverifiable", *, unavailable=True):
        self.reason = reason if type(reason) is str and reason in REASONS else "internal_failure"
        self.unavailable = unavailable
        super().__init__(self.reason)


def require(condition, reason="invalid_input", *, unavailable=False):
    if not condition:
        raise ExecutionError(reason, unavailable=unavailable)


def instant(value):
    require(type(value) is datetime and value.tzinfo is not None
            and value.utcoffset().total_seconds() == 0)
    delta = value - datetime(1970, 1, 1, tzinfo=timezone.utc)
    return delta.days * 86400000000 + delta.seconds * 1000000 + delta.microseconds


def utc(value):
    from datetime import timedelta
    require(type(value) is int and value >= 0)
    return datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(microseconds=value)


def identifier(value):
    require(type(value) is str and SAFE_ID.fullmatch(value) is not None)
    return value


def uuid(value):
    try:
        require(type(value) is str and str(UUID(value, version=4)) == value)
    except (ValueError, TypeError):
        raise ExecutionError("invalid_input", unavailable=False) from None
    return value


@dataclass(frozen=True, slots=True, repr=False)
class LaboratoryAccess:
    principal_id: str
    organization_id: str
    role: str
    expires_at: datetime


@dataclass(frozen=True, slots=True, repr=False)
class ProcessingLease:
    reference: str

    def __reduce_ex__(self, protocol):
        raise TypeError("Execution lease is not portable")


@dataclass(slots=True, repr=False)
class ExecutionOwner:
    envelope: AIProcessingEnvelope | None = None
    evidence: SourceEvidence | None = None
    source_bytes: bytes | None = None
    question_bytes: bytes | None = None
    input_bytes: bytes | None = None
    candidate: bytes | None = None
    original_source: bytes | None = None
    original_question: bytes | None = None
    original_input: bytes | None = None
    metadata: dict = field(default_factory=dict)
    decision: object = None
    grant: object = None
    profile: object = None
    authority: object = None
    lease: object = None
    entries: int = 0
    started: int = 0
    input_units: int = 0
    output_units: int = 0
    output_bytes: int = 0
    result_code: str | None = None
    elapsed_us: int = 0
    attempt_version: int = 1
    done: bool = False
    consuming: bool = False
    admission_held: bool = False
    intent_confirmed: bool = False

    def clear(self):
        for name in ("envelope", "evidence", "source_bytes", "question_bytes", "input_bytes", "candidate",
                     "original_source", "original_question", "original_input", "decision", "grant", "profile", "authority", "lease"):
            object.__setattr__(self, name, None)
        self.done = True


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    state: str
    reason: str
    entries: int = 0
    processing_started: int = 0
    input_units: int = 0
    output_units: int = 0


class ExecutionBoundary(Protocol):
    """Trusted composition only; implementation/authority issuers exist in tests."""
    def recognizes_envelope(self, envelope): ...
    def recognizes_source(self, evidence, envelope): ...
    def connector_snapshot(self): ...
    def populate(self, owner): ...
    def authority(self, owner): ...


class ProcessingExecutionLedger(Protocol):
    """Metadata commands only. Consumers never receive a database transaction."""
    def policy(self, access): ...
    def reserve(self, access, metadata): ...
    def consume(self, access, metadata, version): ...
    def observe_entry(self, access, metadata, version): ...
    def finish(self, access, metadata, version, state, reason, reservation, usage): ...
