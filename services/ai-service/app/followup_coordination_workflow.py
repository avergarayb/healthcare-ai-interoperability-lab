"""Internal progress of an already recorded follow-up coordination request.

Creation stays in CONTROLLED_ACTION_V1. This module only moves a stored
request from requested to in progress, then to completed. It does not write
FHIR, send a message, or schedule an appointment.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.followup_coordination_action import (
    CoordinationRequestStatus,
    FollowUpCoordinationRequest,
)
from app.followup_review import validate_review_case_id, validate_utc_timestamp
from app.human_attribution import (
    DevelopmentPrincipalSnapshot,
    validate_development_principal_snapshot,
)


COORDINATION_WORKFLOW_V1 = "COORDINATION_WORKFLOW_V1"
_ALLOWED = (
    (CoordinationRequestStatus.REQUESTED, CoordinationRequestStatus.IN_PROGRESS),
    (CoordinationRequestStatus.IN_PROGRESS, CoordinationRequestStatus.COMPLETED),
)


class CoordinationRequestNotFound(Exception):
    """No coordination request exists for the supplied identifier."""


class CoordinationTransitionRejected(Exception):
    """The stored status does not allow this transition."""


@dataclass(frozen=True)
class CoordinationRequestEvent:
    event_id: str
    coordination_request_id: str
    review_case_id: str
    from_status: CoordinationRequestStatus
    to_status: CoordinationRequestStatus
    principal_id: str
    authenticator_id: str
    session_id: str
    occurred_at: str


@dataclass(frozen=True)
class CoordinationQueueItem:
    request: FollowUpCoordinationRequest
    case_id: str


@dataclass(frozen=True)
class CoordinationRequestDetail:
    request: FollowUpCoordinationRequest
    case_id: str
    review_status: str
    events: tuple[CoordinationRequestEvent, ...]


@dataclass(frozen=True)
class CoordinationTransitionResult:
    request: FollowUpCoordinationRequest
    applied: bool


def transition_is_allowed(
    expected_status: CoordinationRequestStatus,
    target_status: CoordinationRequestStatus,
) -> bool:
    return (expected_status, target_status) in _ALLOWED


def validate_coordination_event(event: CoordinationRequestEvent) -> CoordinationRequestEvent:
    if validate_review_case_id(event.event_id) != event.event_id:
        raise ValueError("coordination event id is invalid")
    if validate_review_case_id(event.coordination_request_id) != event.coordination_request_id:
        raise ValueError("coordination event request id is invalid")
    if validate_review_case_id(event.review_case_id) != event.review_case_id:
        raise ValueError("coordination event review case id is invalid")
    if not transition_is_allowed(event.from_status, event.to_status):
        raise ValueError("coordination event transition is invalid")
    validate_development_principal_snapshot(
        DevelopmentPrincipalSnapshot(
            event.principal_id,
            event.authenticator_id,
            event.session_id,
        )
    )
    validate_utc_timestamp(event.occurred_at)
    return event
