"""Final conjunction. ALLOW_PROCESSING and a derived match are separate checks."""
from ..enterprise_connectors.models import ConnectorFailure, Gate, Reason
from .execution_types import ExecutionError
from .grounding import GroundingRecord
from .models import PROFILE_ID, ProcessingOutcome, ProcessingReason
from .policy import GateCPolicyEvaluator


_AUDIT_REASONS = {
    "derived_delivery_not_granted", "scope_mismatch", "authority_unverifiable",
    "authorization_expired", "policy_changed", "revision_conflict", "lease_invalid", "internal_failure",
}
_PUBLIC = {
    "derived_delivery_not_granted": "processing_not_granted",
    "scope_mismatch": "scope_mismatch",
    "authority_unverifiable": "authority_unverifiable",
    "authorization_expired": "authorization_expired",
    "policy_changed": "policy_changed",
    "revision_conflict": "revision_conflict",
    "lease_invalid": "lease_invalid",
    "internal_failure": "internal_failure",
}


def audit_reason(reason):
    return reason if reason in _AUDIT_REASONS else "internal_failure"


def public_reason(reason):
    if reason == "accepted":
        return "accepted"
    if reason == "processing_not_granted":
        return "processing_not_granted"
    return _PUBLIC.get(reason, "internal_failure")


def _usable(record):
    if type(record) is not GroundingRecord:
        return False
    if record.verdict == "EVIDENCE_FOUND":
        return type(record.days) is int and type(record.months) is int
    return record.verdict == "EVIDENCE_INSUFFICIENT" and record.days is None and record.months is None


def final_permit(boundary, ledger, executor):
    """Re-read no document. Returns whether A, B, C and the recognized grounding still hold."""
    record = boundary._grounding
    if boundary.state != "EXECUTED" or boundary._bound is None or not _usable(record):
        return False, "lease_invalid"
    if boundary._envelope is None or boundary._evidence is None or boundary._context is None:
        return False, "lease_invalid"
    if boundary._envelope.profile_id != PROFILE_ID:
        return False, "profile_denied"
    try:
        snapshot = boundary.connector_snapshot()
        policy = ledger.policy(executor)
        try:
            read = boundary._service.policy.evaluate(snapshot, boundary._context, boundary._request, Gate.READ)
            delivery = boundary._service.policy.evaluate(snapshot, boundary._context, boundary._request, Gate.DELIVERY)
        except ConnectorFailure as error:
            if error.reason in {Reason.EXPIRED, Reason.CREDENTIAL_EXPIRED}:
                return False, "authorization_expired"
            return False, "policy_changed" if error.reason == Reason.STALE else "processing_not_granted"
        if read.expires_at <= boundary._clock() or delivery.expires_at <= boundary._clock():
            return False, "authorization_expired"
        decision = GateCPolicyEvaluator(boundary._service.policy, boundary).evaluate(
            snapshot, policy, boundary._envelope, boundary._evidence)
    except ExecutionError as error:
        return False, error.reason
    except Exception:
        return False, "authority_unverifiable"
    if decision.outcome is not ProcessingOutcome.ALLOW_PROCESSING:
        if decision.reason is ProcessingReason.EXPIRED:
            return False, "authorization_expired"
        if decision.reason is ProcessingReason.STALE:
            return False, "policy_changed"
        if decision.outcome is ProcessingOutcome.UNAVAILABLE:
            return False, "authority_unverifiable"
        return False, "processing_not_granted"
    return True, "accepted"
