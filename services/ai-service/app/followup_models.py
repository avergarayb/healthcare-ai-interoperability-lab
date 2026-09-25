"""Closed HTTP contracts for the Follow-up Agent. Governance fields are application-owned."""

from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

AGENT_NAME = "follow-up-agent"
AGENT_VERSION = "follow-up-agent-v1"
PROMPT_VERSION = "follow-up-agent-v2"
MAX_SUMMARY_CHARS = 2000

CASE_IDS = (
    "SYN-FOLLOWUP-001",
    "SYN-FOLLOWUP-002",
    "SYN-FOLLOWUP-003",
    "SYN-FOLLOWUP-004",
    "SYN-FOLLOWUP-005",
    "SYN-FOLLOWUP-006",
)

FollowUpCaseId = Literal[
    "SYN-FOLLOWUP-001",
    "SYN-FOLLOWUP-002",
    "SYN-FOLLOWUP-003",
    "SYN-FOLLOWUP-004",
    "SYN-FOLLOWUP-005",
    "SYN-FOLLOWUP-006",
]


class FollowUpStatus(str, Enum):
    COMPLETED = "COMPLETED"
    DISABLED = "DISABLED"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    POLICY_DENIED = "POLICY_DENIED"
    PROVIDER_ERROR = "PROVIDER_ERROR"


class FollowUpRequired(str, Enum):
    TRUE = "true"
    FALSE = "false"
    UNKNOWN = "unknown"


class SuggestedActionType(str, Enum):
    REVIEW = "review"
    CONSIDER_FOLLOW_UP = "consider-follow-up"
    NONE = "none"


class FollowUpRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    case_id: FollowUpCaseId = Field(alias="caseId")


class SuggestedAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: SuggestedActionType
    detail: str


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool: str
    id: str


class FollowUpResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    status: FollowUpStatus
    run_id: str = Field(alias="runId")
    agent: Literal["follow-up-agent"] = AGENT_NAME
    agent_version: str = Field(alias="agentVersion")
    case_id: str = Field(alias="caseId")
    follow_up_required: FollowUpRequired = Field(alias="followUpRequired")
    summary: Optional[str] = None
    reason: Optional[str] = None
    suggested_actions: list[SuggestedAction] = Field(alias="suggestedActions")
    evidence: list[Evidence]
    model_called: bool = Field(alias="modelCalled")
    requires_human_review: bool = Field(alias="requiresHumanReview")
    prompt_version: str = Field(alias="promptVersion")

    @field_validator("requires_human_review")
    @classmethod
    def human_review_stays_true(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("requiresHumanReview must remain true")
        return True

    @field_validator("summary")
    @classmethod
    def summary_within_limit(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and len(value) > MAX_SUMMARY_CHARS:
            raise ValueError("summary exceeds limit")
        return value


def followup_response(
    *,
    status: FollowUpStatus,
    run_id: str,
    case_id: str,
    follow_up_required: FollowUpRequired,
    model_called: bool,
    summary: Optional[str] = None,
    reason: Optional[str] = None,
    suggested_actions: Optional[list[SuggestedAction]] = None,
    evidence: Optional[list[Evidence]] = None,
    agent_version: str = AGENT_VERSION,
    prompt_version: str = PROMPT_VERSION,
) -> FollowUpResponse:
    return FollowUpResponse(
        status=status,
        runId=run_id,
        agent=AGENT_NAME,
        agentVersion=agent_version,
        caseId=case_id,
        followUpRequired=follow_up_required,
        summary=summary,
        reason=reason,
        suggestedActions=suggested_actions or [],
        evidence=evidence or [],
        modelCalled=model_called,
        requiresHumanReview=True,
        promptVersion=prompt_version,
    )


def dump_followup_response(response: FollowUpResponse) -> dict:
    return response.model_dump(by_alias=True, mode="json")
