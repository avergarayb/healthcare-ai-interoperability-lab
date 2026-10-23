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
EVENT_TYPES = frozenset({"authentication"})
ACTOR_TYPES = frozenset({"anonymous", "development_principal"})
ACTIONS = frozenset({"authenticate"})
OUTCOMES = frozenset({"allowed", "denied"})
RESOURCE_TYPES = frozenset({"authentication"})
REASON_CODES = frozenset({"credential_accepted", "credential_rejected"})
METADATA_KEYS = frozenset({"route"})


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
