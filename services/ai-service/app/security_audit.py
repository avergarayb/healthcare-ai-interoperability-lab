"""Append-only security audit contract for this process.

The record is an operational event. It is not a clinical document, not a FHIR
resource, and not proof that the SQLite file was protected from an administrator.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Mapping

CONTRACT_VERSION = "security-audit-v1"
SOURCE_SERVICE = "ai-service"
_EVENT_ID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
_SAFE_ID = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,78}[a-z0-9])?$")
_TIMESTAMP = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?Z$")
_METADATA_KEY = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
_METADATA_VALUE = re.compile(r"^[A-Za-z0-9_./:-]{1,80}$")
_WORKFLOW_ID = re.compile(r"^wf-[0-9a-f]{32}$")
_REVIEW_CASE_ID = _EVENT_ID
_CASE_VERSION = re.compile(r"^[1-9][0-9]{0,8}$")
_SENSITIVE_KEY = (
    "token",
    "secret",
    "password",
    "cookie",
    "authorization",
    "credential",
    "apikey",
    "api_key",
)
_SENSITIVE_VALUE = re.compile(
    r"(x-service-token|bearer\s|api[_-]?key|password|cookie|sk-[a-z0-9]|private key)",
    re.IGNORECASE,
)
EVENT_TYPES = frozenset(
    {"authentication", "workflow_start", "workflow_resume", "human_review_decision"}
)
ACTOR_TYPES = frozenset({"anonymous", "development_principal", "service_client"})
ACTIONS = frozenset(
    {"authenticate", "start_workflow", "resume_workflow", "close_review_case"}
)
OUTCOMES = frozenset({"allowed", "denied"})
RESOURCE_TYPES = frozenset({"authentication", "workflow", "human_review_case"})
REASON_CODES = frozenset(
    {
        "credential_accepted",
        "credential_rejected",
        "access_granted",
        "service_token_missing",
        "service_token_invalid",
        "workflow_disabled",
        "workflow_type_not_allowed",
        "human_review_decision_rejected",
        "human_session_missing",
        "human_session_invalid",
        "same_origin_rejected",
        "form_signature_rejected",
    }
)
METADATA_KEYS = frozenset({"route", "workflow_type", "human_decision", "case_version"})

_WORKFLOW_EVENT = {
    "workflow_start": ("start_workflow", "/internal/workflows"),
    "workflow_resume": ("resume_workflow", "/internal/workflows/:workflowId/resume"),
}
_WORKFLOW_TYPES = frozenset({"post_consultation", "missed_follow_up", "cross_org_lab_result"})
_HUMAN_REVIEW_DECISIONS = frozenset(
    {"follow_up_coordination_planned", "review_completed_no_operational_action"}
)
_UNAUTHENTICATED_REASONS = frozenset({"service_token_missing", "service_token_invalid"})
_AUTHENTICATED_DENIAL_REASONS = {
    "workflow_start": frozenset({"workflow_disabled", "workflow_type_not_allowed"}),
    "workflow_resume": frozenset({"workflow_disabled", "human_review_decision_rejected"}),
}
_HUMAN_REVIEW_ANONYMOUS_REASONS = frozenset(
    {"human_session_missing", "human_session_invalid"}
)
_HUMAN_REVIEW_AUTHENTICATED_REASONS = frozenset(
    {"same_origin_rejected", "form_signature_rejected"}
)


class SecurityAuditRejected(ValueError):
    """The event is not safe to store."""


class SecurityAuditUnavailable(RuntimeError):
    """The audit store could not accept the event."""


class SecurityAuditStoreInitializationError(RuntimeError):
    """The audit database could not be prepared."""


@dataclass(frozen=True)
class SecurityAuditEvent:
    event_id: str
    timestamp_utc: str
    event_type: str
    actor_type: str
    actor_id: str
    organization_id: str | None
    source_service: str
    resource_type: str
    resource_reference: str | None
    action: str
    outcome: str
    reason_code: str
    correlation_id: str
    metadata: tuple[tuple[str, str], ...]
    contract_version: str = CONTRACT_VERSION


def utc_now(clock: Callable[[], datetime] | None = None) -> str:
    moment = datetime.now(timezone.utc) if clock is None else clock()
    if moment.tzinfo is None:
        raise SecurityAuditRejected("timestamp must be timezone-aware")
    return moment.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def authentication_event(
    *,
    outcome: str,
    actor_id: str,
    actor_type: str,
    reason_code: str,
    clock: Callable[[], datetime] | None = None,
) -> SecurityAuditEvent:
    """Build one development-login event. The caller supplies no request body."""
    return validate_security_audit_event(
        SecurityAuditEvent(
            event_id=str(uuid.uuid4()),
            timestamp_utc=utc_now(clock),
            event_type="authentication",
            actor_type=actor_type,
            actor_id=actor_id,
            organization_id=None,
            source_service=SOURCE_SERVICE,
            resource_type="authentication",
            resource_reference="development-login",
            action="authenticate",
            outcome=outcome,
            reason_code=reason_code,
            correlation_id=str(uuid.uuid4()),
            metadata=(("route", "/review-login"),),
        )
    )


def audit_correlation_id(candidate: object) -> str:
    """Keep only a canonical UUIDv4 supplied by the caller; otherwise create one."""
    if isinstance(candidate, str):
        try:
            parsed = uuid.UUID(candidate)
        except (ValueError, AttributeError):
            pass
        else:
            if parsed.version == 4 and str(parsed) == candidate:
                return candidate
    return str(uuid.uuid4())


def workflow_security_event(
    *,
    event_type: str,
    outcome: str,
    reason_code: str,
    correlation_id: str,
    authenticated: bool,
    workflow_id: str | None = None,
    workflow_type: str | None = None,
    clock: Callable[[], datetime] | None = None,
) -> SecurityAuditEvent:
    """Build a minimized access-decision event for a workflow boundary."""
    try:
        action, route = _WORKFLOW_EVENT[event_type]
    except (KeyError, TypeError) as exc:
        raise SecurityAuditRejected("workflow event_type is invalid") from exc
    if outcome == "allowed":
        if not authenticated or reason_code != "access_granted":
            raise SecurityAuditRejected("allowed workflow decision is invalid")
    elif outcome == "denied":
        expected = _AUTHENTICATED_DENIAL_REASONS[event_type] if authenticated else _UNAUTHENTICATED_REASONS
        if reason_code not in expected:
            raise SecurityAuditRejected("denied workflow decision is invalid")
    else:
        raise SecurityAuditRejected("workflow outcome is invalid")
    if workflow_type is not None and workflow_type not in _WORKFLOW_TYPES:
        raise SecurityAuditRejected("workflow_type is invalid")
    if workflow_id is not None and (
        not isinstance(workflow_id, str) or _WORKFLOW_ID.fullmatch(workflow_id) is None
    ):
        raise SecurityAuditRejected("workflow_id is invalid")
    metadata = (("route", route),)
    if workflow_type is not None:
        metadata += (("workflow_type", workflow_type),)
    return validate_security_audit_event(
        SecurityAuditEvent(
            event_id=str(uuid.uuid4()),
            timestamp_utc=utc_now(clock),
            event_type=event_type,
            actor_type="service_client" if authenticated else "anonymous",
            actor_id="internal-service" if authenticated else "anonymous",
            organization_id=None,
            source_service=SOURCE_SERVICE,
            resource_type="workflow",
            resource_reference=None if workflow_id is None else f"workflow/{workflow_id}",
            action=action,
            outcome=outcome,
            reason_code=reason_code,
            correlation_id=correlation_id,
            metadata=metadata,
        )
    )


def human_review_decision_event(
    *,
    outcome: str,
    reason_code: str,
    correlation_id: str,
    actor_id: str | None = None,
    review_case_id: str | None = None,
    human_decision: str | None = None,
    case_version: int | None = None,
    clock: Callable[[], datetime] | None = None,
) -> SecurityAuditEvent:
    """Build one minimized security decision for the Human Review close boundary.

    ``outcome`` is the access decision. ``human_decision`` is only the bounded
    choice submitted for an allowed new close. Workflow execution is not stored
    by this event.
    """
    authenticated = actor_id is not None
    if outcome == "allowed":
        if not authenticated or reason_code != "access_granted":
            raise SecurityAuditRejected("allowed human review decision is invalid")
        if human_decision not in _HUMAN_REVIEW_DECISIONS:
            raise SecurityAuditRejected("human_decision is invalid")
        if not isinstance(case_version, int) or isinstance(case_version, bool) or case_version < 1:
            raise SecurityAuditRejected("case_version is invalid")
        if review_case_id is None:
            raise SecurityAuditRejected("review_case_id is required")
    elif outcome == "denied":
        expected = (
            _HUMAN_REVIEW_AUTHENTICATED_REASONS
            if authenticated
            else _HUMAN_REVIEW_ANONYMOUS_REASONS
        )
        if reason_code not in expected:
            raise SecurityAuditRejected("denied human review decision is invalid")
        if human_decision is not None or case_version is not None:
            raise SecurityAuditRejected("denied human review metadata is invalid")
    else:
        raise SecurityAuditRejected("human review outcome is invalid")
    if review_case_id is not None and (
        not isinstance(review_case_id, str)
        or _REVIEW_CASE_ID.fullmatch(review_case_id) is None
    ):
        raise SecurityAuditRejected("review_case_id is invalid")
    metadata = (("route", "/review-cases/:reviewCaseId/close"),)
    if outcome == "allowed":
        metadata += (
            ("human_decision", human_decision),
            ("case_version", str(case_version)),
        )
    return validate_security_audit_event(
        SecurityAuditEvent(
            event_id=str(uuid.uuid4()),
            timestamp_utc=utc_now(clock),
            event_type="human_review_decision",
            actor_type="development_principal" if authenticated else "anonymous",
            actor_id=actor_id if authenticated else "anonymous",
            organization_id=None,
            source_service=SOURCE_SERVICE,
            resource_type="human_review_case",
            resource_reference=(
                None if review_case_id is None else f"review-case/{review_case_id}"
            ),
            action="close_review_case",
            outcome=outcome,
            reason_code=reason_code,
            correlation_id=correlation_id,
            metadata=metadata,
        )
    )


def validate_security_audit_event(event: SecurityAuditEvent) -> SecurityAuditEvent:
    if not isinstance(event, SecurityAuditEvent):
        raise SecurityAuditRejected("event type is invalid")
    _exact(event.event_id, _EVENT_ID, "event_id")
    _exact(event.correlation_id, _EVENT_ID, "correlation_id")
    _exact(event.timestamp_utc, _TIMESTAMP, "timestamp_utc")
    _choice(event.event_type, EVENT_TYPES, "event_type")
    _choice(event.actor_type, ACTOR_TYPES, "actor_type")
    _exact(event.actor_id, _SAFE_ID, "actor_id")
    if event.organization_id is not None:
        _exact(event.organization_id, _SAFE_ID, "organization_id")
    if event.source_service != SOURCE_SERVICE:
        raise SecurityAuditRejected("source_service is invalid")
    _choice(event.resource_type, RESOURCE_TYPES, "resource_type")
    if event.resource_reference is not None:
        _exact(event.resource_reference, _METADATA_VALUE, "resource_reference")
    _choice(event.action, ACTIONS, "action")
    _choice(event.outcome, OUTCOMES, "outcome")
    _choice(event.reason_code, REASON_CODES, "reason_code")
    if event.contract_version != CONTRACT_VERSION:
        raise SecurityAuditRejected("contract_version is invalid")
    _metadata(event.metadata)
    _event_contract(event)
    _scan(event)
    return event


def metadata_json(metadata: tuple[tuple[str, str], ...]) -> str:
    return json.dumps(dict(metadata), ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def metadata_from_json(value: str) -> tuple[tuple[str, str], ...]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise SecurityAuditRejected("metadata is invalid") from exc
    if not isinstance(parsed, dict):
        raise SecurityAuditRejected("metadata is invalid")
    pairs = tuple((str(key), parsed[key]) for key in sorted(parsed))
    _metadata(pairs)
    return pairs


def _metadata(metadata: object) -> None:
    if not isinstance(metadata, tuple):
        raise SecurityAuditRejected("metadata is invalid")
    seen: set[str] = set()
    for item in metadata:
        if not isinstance(item, tuple) or len(item) != 2:
            raise SecurityAuditRejected("metadata is invalid")
        key, value = item
        if not isinstance(key, str) or not isinstance(value, str):
            raise SecurityAuditRejected("metadata is invalid")
        lowered = key.lower()
        if lowered in seen or lowered not in METADATA_KEYS or _METADATA_KEY.fullmatch(key) is None:
            raise SecurityAuditRejected("metadata key is not allowed")
        if any(part in lowered for part in _SENSITIVE_KEY):
            raise SecurityAuditRejected("metadata key is not allowed")
        if _METADATA_VALUE.fullmatch(value) is None or _SENSITIVE_VALUE.search(value):
            raise SecurityAuditRejected("metadata value is not allowed")
        seen.add(lowered)


def _event_contract(event: SecurityAuditEvent) -> None:
    """Reject valid individual fields combined outside their event contract."""
    if event.organization_id is not None:
        raise SecurityAuditRejected("organization_id is invalid for this event")
    metadata = dict(event.metadata)
    if event.event_type == "authentication":
        _authentication_contract(event, metadata)
        return
    if event.event_type in _WORKFLOW_EVENT:
        _workflow_contract(event, metadata)
        return
    if event.event_type == "human_review_decision":
        _human_review_contract(event, metadata)
        return
    raise SecurityAuditRejected("event contract is invalid")


def _authentication_contract(event: SecurityAuditEvent, metadata: dict[str, str]) -> None:
    if (
        event.action != "authenticate"
        or event.resource_type != "authentication"
        or event.resource_reference != "development-login"
        or metadata != {"route": "/review-login"}
    ):
        raise SecurityAuditRejected("authentication event contract is invalid")
    expected = (
        ("development_principal", "credential_accepted")
        if event.outcome == "allowed"
        else ("anonymous", "credential_rejected")
    )
    if (event.actor_type, event.reason_code) != expected:
        raise SecurityAuditRejected("authentication decision is invalid")
    if event.outcome == "denied" and event.actor_id != "anonymous":
        raise SecurityAuditRejected("authentication actor is invalid")


def _workflow_contract(event: SecurityAuditEvent, metadata: dict[str, str]) -> None:
    action, route = _WORKFLOW_EVENT[event.event_type]
    if event.action != action or event.resource_type != "workflow" or metadata.get("route") != route:
        raise SecurityAuditRejected("workflow event contract is invalid")
    if set(metadata) - {"route", "workflow_type"}:
        raise SecurityAuditRejected("workflow metadata is invalid")
    workflow_type = metadata.get("workflow_type")
    if workflow_type is not None and workflow_type not in _WORKFLOW_TYPES:
        raise SecurityAuditRejected("workflow_type is invalid")
    if event.resource_reference is not None:
        prefix = "workflow/"
        workflow_id = event.resource_reference[len(prefix) :] if event.resource_reference.startswith(prefix) else ""
        if _WORKFLOW_ID.fullmatch(workflow_id) is None:
            raise SecurityAuditRejected("workflow resource_reference is invalid")
    if event.outcome == "allowed":
        if (
            event.actor_type != "service_client"
            or event.actor_id != "internal-service"
            or event.reason_code != "access_granted"
        ):
            raise SecurityAuditRejected("allowed workflow decision is invalid")
        return
    if event.reason_code in _UNAUTHENTICATED_REASONS:
        expected_actor = ("anonymous", "anonymous")
    elif event.reason_code in _AUTHENTICATED_DENIAL_REASONS[event.event_type]:
        expected_actor = ("service_client", "internal-service")
    else:
        raise SecurityAuditRejected("denied workflow decision is invalid")
    if (event.actor_type, event.actor_id) != expected_actor:
        raise SecurityAuditRejected("workflow actor is invalid")


def _human_review_contract(event: SecurityAuditEvent, metadata: dict[str, str]) -> None:
    if (
        event.action != "close_review_case"
        or event.resource_type != "human_review_case"
        or metadata.get("route") != "/review-cases/:reviewCaseId/close"
    ):
        raise SecurityAuditRejected("human review event contract is invalid")
    reference = event.resource_reference
    review_case_id = (
        reference[len("review-case/") :]
        if isinstance(reference, str) and reference.startswith("review-case/")
        else ""
    )
    valid_reference = _REVIEW_CASE_ID.fullmatch(review_case_id) is not None
    if event.outcome == "allowed":
        if (
            event.actor_type != "development_principal"
            or event.reason_code != "access_granted"
            or not valid_reference
            or set(metadata) != {"route", "human_decision", "case_version"}
            or metadata.get("human_decision") not in _HUMAN_REVIEW_DECISIONS
            or _CASE_VERSION.fullmatch(metadata.get("case_version", "")) is None
        ):
            raise SecurityAuditRejected("allowed human review decision is invalid")
        return
    if event.reason_code in _HUMAN_REVIEW_ANONYMOUS_REASONS:
        if (
            event.actor_type != "anonymous"
            or event.actor_id != "anonymous"
            or reference is not None
        ):
            raise SecurityAuditRejected("anonymous human review denial is invalid")
    elif event.reason_code in _HUMAN_REVIEW_AUTHENTICATED_REASONS:
        if event.actor_type != "development_principal" or not valid_reference:
            raise SecurityAuditRejected("authenticated human review denial is invalid")
    else:
        raise SecurityAuditRejected("denied human review decision is invalid")
    if set(metadata) != {"route"}:
        raise SecurityAuditRejected("denied human review metadata is invalid")


def _scan(event: SecurityAuditEvent) -> None:
    fields = (
        event.event_id,
        event.timestamp_utc,
        event.event_type,
        event.actor_type,
        event.actor_id,
        event.organization_id or "",
        event.source_service,
        event.resource_type,
        event.resource_reference or "",
        event.action,
        event.outcome,
        event.reason_code,
        event.correlation_id,
        metadata_json(event.metadata),
        event.contract_version,
    )
    for field in fields:
        if _SENSITIVE_VALUE.search(field):
            raise SecurityAuditRejected("event contains restricted content")


def _exact(value: object, pattern: re.Pattern[str], name: str) -> None:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise SecurityAuditRejected(f"{name} is invalid")


def _choice(value: object, allowed: frozenset[str], name: str) -> None:
    if not isinstance(value, str) or value not in allowed:
        raise SecurityAuditRejected(f"{name} is invalid")


def reject_untrusted_metadata(value: Mapping[object, object]) -> None:
    """Validate a caller-supplied map before it can reach the repository."""
    if not isinstance(value, Mapping):
        raise SecurityAuditRejected("metadata is invalid")
    pairs = []
    for key, item in value.items():
        if not isinstance(key, str) or not isinstance(item, str):
            raise SecurityAuditRejected("metadata is invalid")
        pairs.append((key, item))
    _metadata(tuple(pairs))
