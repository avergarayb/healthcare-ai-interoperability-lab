"""Pure C01 eligibility. No store, audit, model, lease, credential or tool effects."""
from dataclasses import fields
from datetime import datetime, timedelta
from uuid import UUID

from ..enterprise_connectors.models import (
    ConnectorExecutionContext, ConnectorFailure, ConnectorOperation, Gate, OperationRequest, Reason,
)
from ..enterprise_connectors.policy import PolicyEvaluator
from ..enterprise_connectors.registry import PolicySnapshot, SAFE_ID
from .models import (
    AIProcessingDecision, AIProcessingEnvelope, AIProcessingGrant, AIProcessingPolicy, CLASSIFICATION,
    DESTINATION, ModelProcessingProfile, PROCESSING_OPERATION, PROCESSING_PURPOSE, PROFILE_ID,
    ProcessingBoundary, ProcessingLimits, ProcessingOutcome as Outcome, ProcessingReason as R,
    RETENTION, SourceEvidence,
)


class _Rejected(Exception):
    def __init__(self, reason, *, unavailable=False):
        self.reason, self.unavailable = reason, unavailable
        super().__init__(reason.value)


def _require(condition, reason, *, unavailable=False):
    if not condition:
        raise _Rejected(reason, unavailable=unavailable)


def _recognized(value, reason):
    _require(type(value) is bool, R.UNVERIFIABLE, unavailable=True)
    _require(value, reason)


def _positive(value):
    return type(value) is int and 0 < value <= 1_000_000


def _question_bytes(value):
    try:
        return len(value.encode("utf-8"))
    except UnicodeEncodeError:
        raise _Rejected(R.INPUT) from None


def _utc(value):
    return type(value) is datetime and value.tzinfo is not None and value.utcoffset() == timedelta(0)


def _uuid(value):
    try:
        return type(value) is str and str(UUID(value, version=4)) == value
    except ValueError:
        return False


def _closed_scalars(record):
    # Existing connector records use postponed annotations; do not silently
    # skip their scalar fields or evaluate arbitrary annotation expressions.
    scalars = {str: str, int: int, bool: bool, datetime: datetime,
               "str": str, "int": int, "bool": bool, "datetime": datetime}
    return all(type(getattr(record, f.name)) is scalars[f.type]
               for f in fields(record) if f.type in scalars)


def _ids(record):
    return all(type(value := getattr(record, f.name)) is str and SAFE_ID.fullmatch(value)
               for f in fields(record) if f.name.endswith("_id") or f.name in {"source_ref", "binding_id"})


def _limits_shape(limits):
    return type(limits) is ProcessingLimits and all(
        type(value := getattr(limits, f.name)) is int and (value == 0 if f.name == "max_retries" else _positive(value))
        for f in fields(limits))


def _within(requested, ceiling):
    return all(getattr(requested, f.name) <= getattr(ceiling, f.name) for f in fields(requested))


def _dates(record, now):
    _require(all(_utc(getattr(record, name)) for name in ("valid_from", "expires_at", "review_due_at")),
             R.UNVERIFIABLE, unavailable=True)
    _require(record.valid_from <= now < min(record.expires_at, record.review_due_at), R.EXPIRED)
    return min(record.expires_at, record.review_due_at)


def _policy_shape(policy):
    _require(_positive(policy.revision), R.UNVERIFIABLE, unavailable=True)
    for rows, row_type, key in ((policy.grants, AIProcessingGrant, "grant_id"),
                                (policy.profiles, ModelProcessingProfile, "profile_id")):
        _require(type(rows) is tuple and len(rows) <= 32, R.UNVERIFIABLE, unavailable=True)
        _require(all(type(row) is row_type for row in rows), R.UNVERIFIABLE, unavailable=True)
        _require(len({(row.organization_id, getattr(row, key)) for row in rows}) == len(rows),
                 R.UNVERIFIABLE, unavailable=True)
        for row in rows:
            _require(_closed_scalars(row) and _ids(row) and type(row.enabled) is bool and _positive(row.version)
                     and _limits_shape(row.limits)
                     and all(_utc(getattr(row, name)) for name in ("valid_from", "expires_at", "review_due_at")),
                     R.UNVERIFIABLE, unavailable=True)


class GateCPolicyEvaluator:
    """Explicit trusted composition only. An ALLOW result cannot execute anything.

    Boundary recognizers must be pure and use already captured trusted records.
    The existing connector policy owns identity, resource resolution and A/B.
    """
    def __init__(self, connector_policy: PolicyEvaluator, boundary: ProcessingBoundary):
        if type(connector_policy) is not PolicyEvaluator:
            raise ValueError("Existing connector policy required")
        self._connector, self._boundary = connector_policy, boundary

    def evaluate(self, connector_snapshot, processing_policy, envelope, evidence) -> AIProcessingDecision:
        try:
            return self._evaluate(connector_snapshot, processing_policy, envelope, evidence)
        except _Rejected as error:
            return AIProcessingDecision(Outcome.UNAVAILABLE if error.unavailable else Outcome.DENY, error.reason)
        except ConnectorFailure as error:
            unavailable = error.unavailable or error.reason == Reason.POLICY
            reason = R.UNVERIFIABLE if unavailable else (
                R.EXPIRED if error.reason in {Reason.EXPIRED, Reason.CREDENTIAL_EXPIRED} else R.SCOPE)
            return AIProcessingDecision(Outcome.UNAVAILABLE if unavailable else Outcome.DENY, reason)
        except Exception:
            # Never expose error text, records or arbitrary dependency data.
            return AIProcessingDecision(Outcome.UNAVAILABLE, R.UNVERIFIABLE)

    def _evaluate(self, snapshot, policy, envelope, source):
        _require(type(snapshot) is PolicySnapshot and type(policy) is AIProcessingPolicy
                 and type(envelope) is AIProcessingEnvelope and type(source) is SourceEvidence, R.INPUT)
        _recognized(self._boundary.recognizes_envelope(envelope), R.IDENTITY)
        _recognized(self._boundary.recognizes_policy(snapshot, policy), R.STALE)
        _recognized(self._boundary.recognizes_source(source, envelope), R.SOURCE)
        _policy_shape(policy)
        now = self._connector.clock()
        _require(_utc(now), R.UNVERIFIABLE, unavailable=True)
        self._envelope(envelope, snapshot, policy, now)
        # Public existing policy only: no copied scope/tenant/principal algorithm.
        read = self._connector.evaluate(snapshot, envelope.context, envelope.read_request, Gate.READ)
        delivery = self._connector.evaluate(snapshot, envelope.context, envelope.read_request, Gate.DELIVERY)
        self._source(source, envelope, read, now)
        _require(envelope.limits.max_source_bytes <= read.definition.limits.max_bytes
                 and envelope.limits.max_seconds <= read.definition.limits.max_seconds
                 and envelope.limits.max_concurrent <= read.definition.limits.max_concurrent, R.LIMIT)
        profile = self._profile(policy, envelope, source, now)
        self._budgets(envelope, source, profile.limits)
        grant_expiry = self._grant(policy, envelope, source, profile, now)
        expires = min(envelope.expires_at, read.expires_at, delivery.expires_at,
                      _dates(profile, now), grant_expiry,
                      envelope.issued_at + timedelta(seconds=envelope.limits.max_seconds))
        _require(self._connector.clock() < expires, R.EXPIRED)
        return AIProcessingDecision(Outcome.ALLOW_PROCESSING, R.ALLOWED, envelope.operation_id,
                                    source.organization_id, source.resource_id,
                                    snapshot.revision, policy.revision, expires)

    def _envelope(self, e, snapshot, policy, now):
        _require(type(e.context) is ConnectorExecutionContext and type(e.read_request) is OperationRequest,
                 R.INPUT)
        _require(_closed_scalars(e) and _closed_scalars(e.context) and _ids(e.context)
                 and _closed_scalars(e.read_request) and _ids(e.read_request)
                 and _ids(e) and _uuid(e.operation_id), R.INPUT)
        _require(all(_positive(value) for value in (e.registered_version, e.content_revision,
                     e.connector_revision, e.processing_revision, e.profile_version)), R.INPUT)
        _require(e.connector_revision == e.read_request.policy_version == snapshot.revision
                 and e.processing_revision == policy.revision, R.STALE)
        _require(_utc(e.issued_at) and _utc(e.expires_at) and _utc(e.context.authenticated_at)
                 and _utc(e.context.expires_at), R.INPUT)
        _require(e.issued_at <= now < e.expires_at <= e.context.expires_at
                 and e.expires_at <= e.issued_at + timedelta(seconds=5), R.EXPIRED)
        _require(e.read_request.operation is ConnectorOperation.READ
                 and e.processing_operation == PROCESSING_OPERATION, R.SCOPE)
        _require(type(e.processing_purpose) is str and e.processing_purpose == PROCESSING_PURPOSE, R.PURPOSE)
        _require(type(e.question) is str, R.INPUT)
        _require(0 < len(e.question) <= 256 and _question_bytes(e.question) <= 256, R.LIMIT)
        _require(_limits_shape(e.limits) and _within(e.limits, ProcessingLimits()), R.LIMIT)

    def _source(self, s, e, read, now):
        r, b = read.resource, read.binding
        _require(_closed_scalars(s) and _ids(s) and _uuid(s.read_correlation_id)
                 and _positive(s.registered_version) and _positive(s.connector_revision), R.SOURCE)
        _require(type(s.utf8_bytes) is int and s.utf8_bytes > 0 and _positive(s.content_revision), R.SOURCE)
        _require(_utc(s.observed_at) and s.observed_at <= e.issued_at <= now, R.SOURCE)
        _require((s.organization_id, s.instance_id, s.tenant_id, s.resource_id, s.registered_version,
                  s.content_revision, s.connector_revision, s.source_ref, s.classification)
                 == (e.context.organization_id, e.read_request.instance_id, b.tenant_id,
                     e.read_request.resource_id, r.version, e.content_revision, e.connector_revision,
                     e.source_ref, r.classification), R.SOURCE)
        _require(e.binding_id == b.binding_id and e.tenant_id == b.tenant_id
                 and e.registered_version == r.version, R.SCOPE)
        _require(s.provenance == "synthetic-documents-v1", R.SOURCE)

    def _profile(self, policy, e, source, now):
        matches = [p for p in policy.profiles if p.organization_id == e.context.organization_id
                   and p.profile_id == e.profile_id]
        _require(len(matches) == 1, R.PROFILE)
        p = matches[0]
        _require(p.enabled and p.version == e.profile_version, R.PROFILE)
        _dates(p, now)
        _require((p.profile_id, p.provider, p.model_id, p.model_version, p.destination, p.tokenizer)
                 == (PROFILE_ID, "fake", PROFILE_ID, "1", DESTINATION, "fake-byte-v1"), R.PROFILE)
        _require(type(p.questions) is frozenset and 0 < len(p.questions) <= 4
                 and all(type(q) is str for q in p.questions), R.UNVERIFIABLE, unavailable=True)
        _require(e.question in p.questions, R.PURPOSE)
        _require(p.classification == source.classification == CLASSIFICATION, R.CLASSIFICATION)
        _require(p.processing_purpose == e.processing_purpose, R.PURPOSE)
        _require(p.retention == RETENTION, R.RETENTION)
        return p

    def _budgets(self, envelope, source, ceiling):
        limits = envelope.limits
        _require(_within(limits, ceiling) and _within(ceiling, ProcessingLimits()), R.LIMIT)
        _require(source.utf8_bytes <= limits.max_source_bytes
                 and _question_bytes(envelope.question) <= limits.max_question_bytes
                 and source.utf8_bytes + _question_bytes(envelope.question) <= limits.max_input_bytes,
                 R.LIMIT)

    def _grant(self, policy, e, source, profile, now):
        expected = (e.context.principal_id, e.context.principal_type, e.context.organization_id,
                    e.read_request.instance_id, e.tenant_id, e.read_request.resource_id,
                    e.read_request.operation, e.read_request.purpose, e.processing_operation,
                    e.processing_purpose, e.read_request.recipient_id, source.classification,
                    profile.profile_id, profile.version)
        eligible = []
        rejection = R.GRANT
        for grant in policy.grants:
            actual = (grant.principal_id, grant.principal_type, grant.organization_id, grant.instance_id,
                      grant.tenant_id, grant.resource_id, grant.read_operation, grant.read_purpose,
                      grant.processing_operation, grant.processing_purpose, grant.recipient_id,
                      grant.classification, grant.profile_id, grant.profile_version)
            if not grant.enabled or actual != expected:
                continue
            try:
                _require(grant.approval == "not_required", R.APPROVAL)
                _require(type(grant.read_operation) is ConnectorOperation and _positive(grant.profile_version), R.GRANT)
                self._budgets(e, source, grant.limits)
                eligible.append(_dates(grant, now))
            except _Rejected as error:
                if error.unavailable:
                    raise
                rejection = error.reason
        _require(bool(eligible), rejection)
        return max(eligible)  # One complete grant, never merge partial permissions.
