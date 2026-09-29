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


class PatientRead(str, Enum):
    NOT_READ = "not_read"
    RESOLVED = "resolved"
    NOT_RESOLVED = "not_resolved"
    UNAVAILABLE = "unavailable"


class ObservationRead(str, Enum):
    NOT_READ = "not_read"
    WITH_RESOURCES = "with_resources"
    EMPTY = "empty"
    UNAVAILABLE = "unavailable"


class ScheduleCheck(str, Enum):
    NOT_CHECKED = "not_checked"
    CHECKED = "checked"
    UNAVAILABLE = "unavailable"


class AppointmentClassification(str, Enum):
    UPCOMING_CONFIRMED = "UPCOMING_CONFIRMED"
    UPCOMING_UNCONFIRMED = "UPCOMING_UNCONFIRMED"
    CANCELLED = "CANCELLED"
    PAST = "PAST"
    OTHER = "OTHER"
    NONE = "NONE"


class ClinicalAssessmentStatus(str, Enum):
    NOT_PERFORMED = "not_performed"


class HumanReviewStatus(str, Enum):
    NOT_EVALUATED = "not_evaluated"


class ActionStatus(str, Enum):
    NOT_DETERMINED = "not_determined"


class ContextState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    patient: PatientRead
    observation: ObservationRead


class ScheduleAppointment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    classification: AppointmentClassification


class ScheduleState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check: ScheduleCheck
    classifications: list[AppointmentClassification] | None = None
    appointments: list[ScheduleAppointment] | None = None


class ClinicalAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ClinicalAssessmentStatus


class HumanReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: HumanReviewStatus


class ActionState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ActionStatus


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
    context: ContextState
    schedule: ScheduleState
    clinical_assessment: ClinicalAssessment = Field(alias="clinicalAssessment")
    human_review: HumanReview = Field(alias="humanReview")
    action: ActionState
    follow_up_required: FollowUpRequired = Field(alias="followUpRequired")
    answer: str
    evidence: list[Evidence]


def dump_followup_endpoint_response(response: FollowUpEndpointResponse) -> dict:
    return response.model_dump(by_alias=True, mode="json", exclude_none=True)
