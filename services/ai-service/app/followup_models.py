"""HTTP contracts for POST /internal/agent/follow-up."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

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


class FollowUpRequired(str, Enum):
    TRUE = "true"
    FALSE = "false"
    UNKNOWN = "unknown"


class FollowUpRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    case_id: FollowUpCaseId = Field(alias="caseId")


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool: str
    id: str


class FollowUpEndpointStatus(str, Enum):
    COMPLETED = "completed"
    DENIED = "denied"
    UNAVAILABLE = "unavailable"
    LIMIT = "limit"


class FollowUpEndpointResponse(BaseModel):
    """HTTP projection of FollowUpWorkflowResult."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    run_id: str = Field(alias="runId")
    case_id: str = Field(alias="caseId")
    status: FollowUpEndpointStatus
    follow_up_required: FollowUpRequired = Field(alias="followUpRequired")
    answer: str
    evidence: list[Evidence]


def dump_followup_endpoint_response(response: FollowUpEndpointResponse) -> dict:
    return response.model_dump(by_alias=True, mode="json")
