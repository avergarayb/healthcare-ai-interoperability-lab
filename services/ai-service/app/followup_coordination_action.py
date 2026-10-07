"""Durable follow-up coordination requests.

The repository stores one internal request for an existing review case.
FollowUpCoordinationActionService authorizes that request from the durable
review case before storage. It does not display or send the request.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from app.followup_review import (
    FollowUpReviewCase,
    ReviewCaseNotFound,
    ReviewCaseStatus,
    ReviewOutcome,
    validate_review_case_id,
    validate_utc_timestamp,
)
from app.missed_follow_up_review import MISSED_FOLLOW_UP_REVIEW_V1
from app.post_consultation_review import POST_CONSULTATION_RESULT_REVIEW_V1


CONTROLLED_ACTION_IDENTITY_V1 = "CONTROLLED_ACTION_IDENTITY_V1"
FOLLOW_UP_COORDINATION_ACTION_POLICY_V1 = "FOLLOW_UP_COORDINATION_ACTION_POLICY_V1"
PERSISTABLE_PROTOCOL_IDS = frozenset(
    {
        POST_CONSULTATION_RESULT_REVIEW_V1,
        MISSED_FOLLOW_UP_REVIEW_V1,
    }
)
_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")


class CoordinationActionType(str, Enum):
    CREATE_FOLLOW_UP_COORDINATION_REQUEST = "create_follow_up_coordination_request"


class CoordinationRequestStatus(str, Enum):
    REQUESTED = "requested"


class CoordinationRequestNotPersistable(Exception):
    """The review case protocol cannot be stored on a coordination request."""


class CoordinationPolicyDecision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"


class CoordinationPolicyDenyReason(str, Enum):
    CASE_NOT_CLOSED = "case_not_closed"
    OUTCOME_NOT_AUTHORIZED = "outcome_not_authorized"
    PROTOCOL_NOT_SUPPORTED = "protocol_not_supported"
    ACTION_NOT_SUPPORTED = "action_not_supported"


class CoordinationActionDenied(Exception):
    """The coordination policy did not authorize the request."""

    def __init__(self, result: "CoordinationActionPolicyResult") -> None:
        self.result = result
        reason = result.reason.value if result.reason is not None else "denied"
        super().__init__(reason)


@dataclass(frozen=True)
class CoordinationActionPolicyResult:
    policy_id: str
    decision: CoordinationPolicyDecision
    reason: CoordinationPolicyDenyReason | None


@dataclass(frozen=True)
class FollowUpCoordinationRequest:
    id: str
    action_identity: str
    review_case_id: str
    protocol_id: str
    action_type: CoordinationActionType
    status: CoordinationRequestStatus
    created_at: str


def build_coordination_action_identity(review_case_id: str) -> str:
    """SHA-256 of the canonical action identity for one review case."""
    canonical_id = validate_review_case_id(review_case_id)
    if canonical_id != review_case_id:
        raise ValueError("review case id is invalid")
    payload = {
        "actionType": CoordinationActionType.CREATE_FOLLOW_UP_COORDINATION_REQUEST.value,
        "identitySchema": CONTROLLED_ACTION_IDENTITY_V1,
        "reviewCaseId": canonical_id,
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def persistable_protocol_id(protocol_id: str) -> str:
    """Return a protocol id the coordination table can store.

    The value must already have been read from the durable review case.
    Closed state and outcome are not decided here.
    """
    if protocol_id not in PERSISTABLE_PROTOCOL_IDS:
        raise CoordinationRequestNotPersistable
    return protocol_id


def validate_coordination_request(
    request: FollowUpCoordinationRequest,
) -> FollowUpCoordinationRequest:
    if validate_review_case_id(request.id) != request.id:
        raise ValueError("persisted coordination request id is not canonical")
    if validate_review_case_id(request.review_case_id) != request.review_case_id:
        raise ValueError("persisted coordination review case id is not canonical")
    if (
        not isinstance(request.action_identity, str)
        or _SHA256_HEX.fullmatch(request.action_identity) is None
        or request.action_identity != build_coordination_action_identity(request.review_case_id)
    ):
        raise ValueError("persisted coordination action identity is invalid")
    persistable_protocol_id(request.protocol_id)
    if request.action_type is not CoordinationActionType.CREATE_FOLLOW_UP_COORDINATION_REQUEST:
        raise ValueError("persisted coordination action type is invalid")
    if request.status is not CoordinationRequestStatus.REQUESTED:
        raise ValueError("persisted coordination status is invalid")
    validate_utc_timestamp(request.created_at)
    return request


def evaluate_follow_up_coordination_action_policy(
    case: FollowUpReviewCase,
    *,
    action_type: str,
) -> CoordinationActionPolicyResult:
    """Authorize only from the durable review case and the closed action constant.

    Caller-supplied status, outcome, and protocol are not inputs.
    """
    if case.status is not ReviewCaseStatus.CLOSED:
        return _deny(CoordinationPolicyDenyReason.CASE_NOT_CLOSED)
    if case.outcome is not ReviewOutcome.FOLLOW_UP_COORDINATION_PLANNED:
        return _deny(CoordinationPolicyDenyReason.OUTCOME_NOT_AUTHORIZED)
    if case.protocol_id not in PERSISTABLE_PROTOCOL_IDS:
        return _deny(CoordinationPolicyDenyReason.PROTOCOL_NOT_SUPPORTED)
    if action_type != CoordinationActionType.CREATE_FOLLOW_UP_COORDINATION_REQUEST.value:
        return _deny(CoordinationPolicyDenyReason.ACTION_NOT_SUPPORTED)
    return _allow()


class FollowUpCoordinationActionRepository(Protocol):
    def get(self, review_case_id: str) -> FollowUpReviewCase | None: ...

    def ensure_follow_up_coordination_request(
        self, review_case_id: str
    ) -> FollowUpCoordinationRequest: ...


class FollowUpCoordinationActionService:
    """Authorize from the current durable review case, then store the request.

    A closed review case does not change status, outcome, protocol, or version,
    so an allow decision stays valid until the repository insert.
    """

    def __init__(self, repository: FollowUpCoordinationActionRepository) -> None:
        self._repository = repository

    def ensure_follow_up_coordination_request(
        self, review_case_id: str
    ) -> FollowUpCoordinationRequest:
        validate_review_case_id(review_case_id)
        case = self._repository.get(review_case_id)
        if case is None:
            raise ReviewCaseNotFound
        decision = evaluate_follow_up_coordination_action_policy(
            case,
            action_type=CoordinationActionType.CREATE_FOLLOW_UP_COORDINATION_REQUEST.value,
        )
        if decision.decision is not CoordinationPolicyDecision.ALLOW:
            raise CoordinationActionDenied(decision)
        return self._repository.ensure_follow_up_coordination_request(review_case_id)


def _allow() -> CoordinationActionPolicyResult:
    return CoordinationActionPolicyResult(
        policy_id=FOLLOW_UP_COORDINATION_ACTION_POLICY_V1,
        decision=CoordinationPolicyDecision.ALLOW,
        reason=None,
    )


def _deny(reason: CoordinationPolicyDenyReason) -> CoordinationActionPolicyResult:
    return CoordinationActionPolicyResult(
        policy_id=FOLLOW_UP_COORDINATION_ACTION_POLICY_V1,
        decision=CoordinationPolicyDecision.DENY,
        reason=reason,
    )
