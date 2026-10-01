"""Durable operational review domain for deterministic follow-up matches."""

from __future__ import annotations

import base64
import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Callable, Protocol, Sequence

from app.post_consultation_review import ProtocolEvaluationStatus, ProtocolReviewResult


REVIEW_IDENTITY_SCHEMA = "FOLLOW_UP_REVIEW_EVENT_IDENTITY_V1"
MAX_REASON_CODES = 32
MAX_MATCHED_RESOURCES = 100
MAX_CURSOR_LENGTH = 2048
_FHIR_ID = re.compile(r"^[A-Za-z0-9.-]{1,64}$")
_REASON_CODE = re.compile(r"^[a-z0-9_]{1,128}$")
_CANONICAL_UTC_TIMESTAMP = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$"
)
_RESOURCE_TYPES = frozenset({"Patient", "Encounter", "Observation", "Appointment"})


class ReviewCaseStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"


class ReviewOutcome(str, Enum):
    FOLLOW_UP_COORDINATION_PLANNED = "follow_up_coordination_planned"
    REVIEW_COMPLETED_NO_OPERATIONAL_ACTION = "review_completed_no_operational_action"


class ReviewEventType(str, Enum):
    CREATED = "created"
    CLOSED = "closed"


@dataclass(frozen=True)
class FollowUpReviewTrigger:
    case_id: str
    protocol_id: str
    protocol_evaluation_status: str
    reason_codes: tuple[str, ...]
    matched_resources: tuple[str, ...]
    review_identity: str


@dataclass(frozen=True)
class FollowUpReviewCase:
    id: str
    review_identity: str
    case_id: str
    protocol_id: str
    protocol_evaluation_status: str
    reason_codes: tuple[str, ...]
    matched_resources: tuple[str, ...]
    status: ReviewCaseStatus
    outcome: ReviewOutcome | None
    version: int
    created_at: str
    updated_at: str
    closed_at: str | None


@dataclass(frozen=True)
class FollowUpReviewCaseEvent:
    event_id: str
    review_case_id: str
    case_version: int
    event_type: ReviewEventType
    from_status: ReviewCaseStatus | None
    to_status: ReviewCaseStatus
    outcome: ReviewOutcome | None
    occurred_at: str


@dataclass(frozen=True)
class ReviewCasePage:
    items: tuple[FollowUpReviewCase, ...]
    next_position: tuple[str, str] | None


@dataclass(frozen=True)
class ReviewCaseDetail:
    case: FollowUpReviewCase
    events: tuple[FollowUpReviewCaseEvent, ...]


class ReviewCaseNotFound(Exception):
    """The requested operational review case does not exist."""


class ReviewCaseConflict(Exception):
    """The requested transition conflicts with durable state."""


class ReviewPersistenceUnavailable(Exception):
    """Durable operational review persistence cannot complete the request."""


class ReviewStoreInitializationError(RuntimeError):
    """The product review store cannot be safely initialized."""


class InvalidReviewTrigger(ValueError):
    """A deterministic protocol result cannot form a review event."""


class FollowUpReviewCaseRepository(Protocol):
    def ensure(self, trigger: FollowUpReviewTrigger) -> FollowUpReviewCase: ...

    def get(self, review_case_id: str) -> FollowUpReviewCase | None: ...

    def get_detail(self, review_case_id: str) -> ReviewCaseDetail | None: ...

    def list_cases(
        self,
        *,
        status: ReviewCaseStatus,
        case_id: str | None,
        limit: int,
        after: tuple[str, str] | None,
    ) -> ReviewCasePage: ...

    def close(
        self,
        review_case_id: str,
        *,
        expected_version: int,
        outcome: ReviewOutcome,
    ) -> FollowUpReviewCase: ...

    def events(self, review_case_id: str) -> tuple[FollowUpReviewCaseEvent, ...]: ...


def canonical_matched_resources(resources: Sequence[str]) -> tuple[str, ...]:
    if not resources or len(resources) > MAX_MATCHED_RESOURCES:
        raise InvalidReviewTrigger("matched resources must be non-empty and bounded")
    canonical: set[str] = set()
    for reference in resources:
        if not isinstance(reference, str) or reference.count("/") != 1:
            raise InvalidReviewTrigger("matched resource reference is invalid")
        resource_type, resource_id = reference.split("/", 1)
        if (
            resource_type not in _RESOURCE_TYPES
            or resource_id in {".", ".."}
            or _FHIR_ID.fullmatch(resource_id) is None
        ):
            raise InvalidReviewTrigger("matched resource reference is invalid")
        canonical.add(f"{resource_type}/{resource_id}")
    return tuple(sorted(canonical))


def canonical_reason_codes(reason_codes: Sequence[str]) -> tuple[str, ...]:
    if not reason_codes or len(reason_codes) > MAX_REASON_CODES:
        raise InvalidReviewTrigger("reason codes must be non-empty and bounded")
    canonical: set[str] = set()
    for reason in reason_codes:
        if not isinstance(reason, str) or _REASON_CODE.fullmatch(reason) is None:
            raise InvalidReviewTrigger("reason code is invalid")
        canonical.add(reason)
    return tuple(sorted(canonical))


def build_review_identity(case_id: str, protocol_id: str, matched_resources: Sequence[str]) -> str:
    if not isinstance(case_id, str) or not case_id or len(case_id) > 255:
        raise InvalidReviewTrigger("case id is invalid")
    if not isinstance(protocol_id, str) or not protocol_id or len(protocol_id) > 128:
        raise InvalidReviewTrigger("protocol id is invalid")
    payload = {
        "caseId": case_id,
        "identitySchema": REVIEW_IDENTITY_SCHEMA,
        "matchedResources": list(canonical_matched_resources(matched_resources)),
        "protocolId": protocol_id,
    }
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def trigger_from_protocol(case_id: str, protocol: ProtocolReviewResult) -> FollowUpReviewTrigger:
    if protocol.evaluation_status is not ProtocolEvaluationStatus.MATCHED:
        raise InvalidReviewTrigger("only matched protocol results create review cases")
    resources = canonical_matched_resources(protocol.matched_resources)
    reasons = canonical_reason_codes(protocol.reason_codes)
    return FollowUpReviewTrigger(
        case_id=case_id,
        protocol_id=protocol.id,
        protocol_evaluation_status=protocol.evaluation_status.value,
        reason_codes=reasons,
        matched_resources=resources,
        review_identity=build_review_identity(case_id, protocol.id, resources),
    )


def validate_trigger(trigger: FollowUpReviewTrigger) -> FollowUpReviewTrigger:
    if trigger.protocol_evaluation_status != ProtocolEvaluationStatus.MATCHED.value:
        raise InvalidReviewTrigger("persisted review trigger must be matched")
    resources = canonical_matched_resources(trigger.matched_resources)
    reasons = canonical_reason_codes(trigger.reason_codes)
    identity = build_review_identity(trigger.case_id, trigger.protocol_id, resources)
    if resources != trigger.matched_resources or reasons != trigger.reason_codes:
        raise InvalidReviewTrigger("review trigger provenance must be canonical")
    if identity != trigger.review_identity:
        raise InvalidReviewTrigger("review identity does not match its provenance")
    return trigger


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_timestamp(clock: Callable[[], datetime]) -> str:
    value = clock()
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("durable review clock must return a timezone-aware datetime")
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def validate_review_case_id(value: str) -> str:
    try:
        parsed = uuid.UUID(value)
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("review case id is invalid") from exc
    if parsed.version != 4 or str(parsed) != value.lower():
        raise ValueError("review case id is invalid")
    return str(parsed)


def encode_cursor(
    position: tuple[str, str], *, status: ReviewCaseStatus, case_id: str | None
) -> str:
    payload = {
        "caseId": case_id,
        "createdAt": position[0],
        "id": position[1],
        "status": status.value,
        "v": 1,
    }
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_cursor(
    cursor: str, *, status: ReviewCaseStatus, case_id: str | None
) -> tuple[str, str]:
    if not cursor or len(cursor) > MAX_CURSOR_LENGTH or not re.fullmatch(r"[A-Za-z0-9_-]+", cursor):
        raise ValueError("cursor is invalid")
    try:
        padding = "=" * (-len(cursor) % 4)
        payload = json.loads(
            base64.b64decode(cursor + padding, altchars=b"-_", validate=True),
            object_pairs_hook=_strict_json_object,
        )
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("cursor is invalid") from exc
    if not isinstance(payload, dict) or set(payload) != {"v", "status", "caseId", "createdAt", "id"}:
        raise ValueError("cursor is invalid")
    if payload["v"] != 1 or payload["status"] != status.value or payload["caseId"] != case_id:
        raise ValueError("cursor does not match the query")
    created_at = payload["createdAt"]
    review_case_id = payload["id"]
    if not isinstance(created_at, str) or len(created_at) > 40:
        raise ValueError("cursor is invalid")
    validate_utc_timestamp(created_at)
    validate_review_case_id(review_case_id)
    return created_at, review_case_id


def validate_utc_timestamp(value: str) -> datetime:
    if not isinstance(value, str) or _CANONICAL_UTC_TIMESTAMP.fullmatch(value) is None:
        raise ValueError("timestamp is invalid")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise ValueError("timestamp is invalid") from exc
    return parsed


def validate_review_case(case: FollowUpReviewCase) -> FollowUpReviewCase:
    if not isinstance(case.status, ReviewCaseStatus):
        raise ValueError("persisted review status is invalid")
    if case.outcome is not None and not isinstance(case.outcome, ReviewOutcome):
        raise ValueError("persisted review outcome is invalid")
    if validate_review_case_id(case.id) != case.id:
        raise ValueError("persisted review case id is not canonical")

    created_at = validate_utc_timestamp(case.created_at)
    updated_at = validate_utc_timestamp(case.updated_at)
    if created_at > updated_at:
        raise ValueError("persisted review timestamps are inconsistent")

    validate_trigger(
        FollowUpReviewTrigger(
            case_id=case.case_id,
            protocol_id=case.protocol_id,
            protocol_evaluation_status=case.protocol_evaluation_status,
            reason_codes=case.reason_codes,
            matched_resources=case.matched_resources,
            review_identity=case.review_identity,
        )
    )

    if case.status is ReviewCaseStatus.OPEN:
        if (
            case.version != 1
            or case.outcome is not None
            or case.closed_at is not None
            or case.created_at != case.updated_at
        ):
            raise ValueError("persisted open review case is inconsistent")
        return case

    if (
        case.version != 2
        or case.outcome is None
        or case.closed_at is None
        or case.updated_at != case.closed_at
    ):
        raise ValueError("persisted closed review case is inconsistent")
    closed_at = validate_utc_timestamp(case.closed_at)
    if created_at > closed_at:
        raise ValueError("persisted review timestamps are inconsistent")
    return case


def validate_review_event(event: FollowUpReviewCaseEvent) -> FollowUpReviewCaseEvent:
    if validate_review_case_id(event.event_id) != event.event_id:
        raise ValueError("persisted review event id is not canonical")
    if validate_review_case_id(event.review_case_id) != event.review_case_id:
        raise ValueError("persisted review event case id is not canonical")
    validate_utc_timestamp(event.occurred_at)
    if not isinstance(event.event_type, ReviewEventType):
        raise ValueError("persisted review event type is invalid")
    if event.from_status is not None and not isinstance(event.from_status, ReviewCaseStatus):
        raise ValueError("persisted review event source status is invalid")
    if not isinstance(event.to_status, ReviewCaseStatus):
        raise ValueError("persisted review event target status is invalid")
    if event.outcome is not None and not isinstance(event.outcome, ReviewOutcome):
        raise ValueError("persisted review event outcome is invalid")

    if event.event_type is ReviewEventType.CREATED:
        if (
            event.case_version != 1
            or event.from_status is not None
            or event.to_status is not ReviewCaseStatus.OPEN
            or event.outcome is not None
        ):
            raise ValueError("persisted created event is inconsistent")
        return event

    if (
        event.case_version != 2
        or event.from_status is not ReviewCaseStatus.OPEN
        or event.to_status is not ReviewCaseStatus.CLOSED
        or event.outcome is None
    ):
        raise ValueError("persisted closed event is inconsistent")
    return event


def validate_review_detail(detail: ReviewCaseDetail) -> ReviewCaseDetail:
    case = validate_review_case(detail.case)
    events = tuple(validate_review_event(event) for event in detail.events)
    if any(event.review_case_id != case.id for event in events):
        raise ValueError("persisted review history references another case")
    if len({event.event_id for event in events}) != len(events):
        raise ValueError("persisted review history has duplicate event ids")

    expected_versions = (1,) if case.status is ReviewCaseStatus.OPEN else (1, 2)
    if tuple(event.case_version for event in events) != expected_versions:
        raise ValueError("persisted review history versions are inconsistent")
    if not events or events[0].event_type is not ReviewEventType.CREATED:
        raise ValueError("persisted review history is missing its created event")
    if events[0].occurred_at != case.created_at:
        raise ValueError("persisted created event timestamp is inconsistent")

    if case.status is ReviewCaseStatus.CLOSED:
        closed = events[1]
        if (
            closed.event_type is not ReviewEventType.CLOSED
            or closed.outcome is not case.outcome
            or closed.occurred_at != case.closed_at
        ):
            raise ValueError("persisted closed event is inconsistent with its case")
    return detail


def _strict_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("cursor contains duplicate object keys")
        result[key] = value
    return result


class FollowUpReviewCaseService:
    def __init__(self, repository: FollowUpReviewCaseRepository) -> None:
        self._repository = repository

    def ensure_for_protocol(
        self, case_id: str, protocol: ProtocolReviewResult
    ) -> FollowUpReviewCase | None:
        if protocol.evaluation_status is not ProtocolEvaluationStatus.MATCHED:
            return None
        return self._repository.ensure(trigger_from_protocol(case_id, protocol))

    def get(self, review_case_id: str) -> FollowUpReviewCase:
        case = self._repository.get(review_case_id)
        if case is None:
            raise ReviewCaseNotFound
        return case

    def detail(self, review_case_id: str) -> ReviewCaseDetail:
        detail = self._repository.get_detail(review_case_id)
        if detail is None:
            raise ReviewCaseNotFound
        return detail

    def list_cases(
        self,
        *,
        status: ReviewCaseStatus,
        case_id: str | None,
        limit: int,
        after: tuple[str, str] | None,
    ) -> ReviewCasePage:
        return self._repository.list_cases(status=status, case_id=case_id, limit=limit, after=after)

    def close(
        self,
        review_case_id: str,
        *,
        expected_version: int,
        outcome: ReviewOutcome,
    ) -> FollowUpReviewCase:
        return self._repository.close(
            review_case_id,
            expected_version=expected_version,
            outcome=outcome,
        )

    def events(self, review_case_id: str) -> tuple[FollowUpReviewCaseEvent, ...]:
        return self._repository.events(review_case_id)
