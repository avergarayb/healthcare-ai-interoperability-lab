"""Outbound consumer result. This is not the Java model-boundary contract."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

Status = Literal["received", "rejected"]

Reason = Literal[
    "empty_context",
    "boundary_outcome_not_success",
    "boundary_http_4xx",
    "boundary_http_5xx",
    "boundary_timeout",
    "boundary_connection_error",
    "invalid_contract",
]

RESULT_FIELDS = ("status", "modelCalled", "contractVersion", "outcome", "reason")


class AgentContextResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Status
    modelCalled: bool = Field(default=False)
    contractVersion: Optional[str] = None
    outcome: Optional[str] = None
    reason: Optional[Reason] = None

    @field_validator("modelCalled")
    @classmethod
    def model_is_never_called(cls, value: bool) -> bool:
        if value:
            raise ValueError("modelCalled must remain false")
        return False


def received(*, contract_version: str, outcome: str) -> AgentContextResult:
    return AgentContextResult(
        status="received",
        modelCalled=False,
        contractVersion=contract_version,
        outcome=outcome,
        reason=None,
    )


def rejected(
    *,
    reason: Reason,
    contract_version: Optional[str] = None,
    outcome: Optional[str] = None,
) -> AgentContextResult:
    return AgentContextResult(
        status="rejected",
        modelCalled=False,
        contractVersion=contract_version,
        outcome=outcome,
        reason=reason,
    )
