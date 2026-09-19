"""Closed HTTP contracts for Task 076. Governance fields are application-owned."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

PROMPT_VERSION = "experimental-summary-v1"
PROVIDER_NAME = "GEMINI"
DEFAULT_MODEL = "gemini-2.5-flash"
MAX_SUMMARY_CHARS = 2000
PROVIDER_TIMEOUT_SECONDS = 30

Status = Literal["COMPLETED", "DISABLED", "VALIDATION_ERROR", "PROVIDER_ERROR"]


class ExperimentalObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    display: str
    value: str
    unit: str


class ExperimentalMedication(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    display: str


class ExperimentalSummaryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    case_id: str = Field(alias="caseId")
    patient_age_range: str = Field(alias="patientAgeRange")
    sex: str
    encounter_type: str = Field(alias="encounterType")
    observations: list[ExperimentalObservation]
    medications: list[ExperimentalMedication]


class ExperimentalSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    status: Status
    summary: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    prompt_version: str = Field(alias="promptVersion")
    model_called: bool = Field(alias="modelCalled")
    requires_human_review: bool = Field(alias="requiresHumanReview")

    @field_validator("requires_human_review")
    @classmethod
    def human_review_stays_true(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("requiresHumanReview must remain true")
        return True


def experimental_response(
    *,
    status: Status,
    model_called: bool,
    summary: Optional[str] = None,
    provider: str = PROVIDER_NAME,
    model: str = DEFAULT_MODEL,
) -> ExperimentalSummaryResponse:
    return ExperimentalSummaryResponse(
        status=status,
        summary=summary,
        provider=provider,
        model=model,
        promptVersion=PROMPT_VERSION,
        modelCalled=model_called,
        requiresHumanReview=True,
    )


def dump_response(response: ExperimentalSummaryResponse) -> dict:
    return response.model_dump(by_alias=True)
