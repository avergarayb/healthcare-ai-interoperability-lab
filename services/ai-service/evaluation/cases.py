"""Declarative system scenarios. A scripted token is not a clinical rule."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from app.langgraph_fhir_client import (
    APPOINTMENT_ID,
    APPOINTMENTS_TOOL,
    FOLLOWUP_TOOL,
    PATIENT_CASE,
    PATIENT_ID,
    synthetic_appointment,
)
from app.langgraph_fhir_followup import (
    CANCELLED,
    NONE,
    PAST,
    UPCOMING_CONFIRMED,
    UPCOMING_UNCONFIRMED,
)
from app.langgraph_gemini_fhir_followup import MAX_MODEL_TURNS


MISSING_CASE = "SYN-FOLLOWUP-005"
NO_OBSERVATION_CASE = "SYN-FOLLOWUP-007"
NO_OBSERVATION_PATIENT = "SYN-PATIENT-007"
OBSERVATION_ID = "obs-synthetic-001"
FhirMode = Literal[
    "linked",
    "no_appointments",
    "missing_patient",
    "no_observations",
    "observation_unavailable",
]


@dataclass(frozen=True)
class ToolReply:
    """One scripted tool proposal. The workflow still authorizes it."""

    name: str
    arguments: dict[str, str] | None = None


@dataclass(frozen=True)
class FinalReply:
    """One scripted structured decision. The token checks transport, not clinical truth."""

    follow_up_required: str
    text: str = "Scripted final."


@dataclass(frozen=True)
class UnstructuredReply:
    """A stop without the structured token. The text must not decide the flag."""

    text: str = "The text says follow-up is true."


Reply = ToolReply | FinalReply | UnstructuredReply


@dataclass(frozen=True)
class EvaluationCase:
    """One complete agent situation. It stores expectations, not clinical payloads."""

    id: str
    case_id: str
    replies: tuple[Reply, ...]
    expected_tools: tuple[str, ...]
    expected_status: str
    expected_policy: tuple[tuple[str, str], ...]
    expected_evidence: tuple[tuple[str, str], ...]
    allowed_evidence: tuple[tuple[str, str], ...]
    expected_follow_up_required: str
    expected_structured: bool
    expected_close_count: int
    fhir: FhirMode = "linked"
    max_model_turns: int = field(default_factory=lambda: MAX_MODEL_TURNS)
    expected_classifications: tuple[str, ...] | None = None
    appointment_records: tuple[dict[str, object], ...] | None = None


def _context(case_id: str = PATIENT_CASE) -> ToolReply:
    return ToolReply(FOLLOWUP_TOOL, {"case_id": case_id})


def _appointments(case_id: str = PATIENT_CASE) -> ToolReply:
    return ToolReply(APPOINTMENTS_TOOL, {"case_id": case_id})


_CONTEXT_EVIDENCE = (
    (FOLLOWUP_TOOL, f"Patient/{PATIENT_ID}"),
    (FOLLOWUP_TOOL, f"Observation/{OBSERVATION_ID}"),
)
_APPOINTMENT_EVIDENCE = ((APPOINTMENTS_TOOL, f"Appointment/{APPOINTMENT_ID}"),)
_BOTH_EVIDENCE = _CONTEXT_EVIDENCE + _APPOINTMENT_EVIDENCE


def _schedule_case(
    case_name: str,
    *,
    appointments: tuple[dict[str, object], ...] | None,
    classification: tuple[str, ...],
    evidence: tuple[tuple[str, str], ...],
    follow_up_required: str,
) -> EvaluationCase:
    """One agenda fact. The scripted token is transport, not a consequence of the classification."""
    return EvaluationCase(
        id=case_name,
        case_id=PATIENT_CASE,
        replies=(_context(), _appointments(), FinalReply(follow_up_required)),
        expected_tools=(FOLLOWUP_TOOL, APPOINTMENTS_TOOL),
        expected_status="finish",
        expected_policy=((FOLLOWUP_TOOL, "allowed"), (APPOINTMENTS_TOOL, "allowed")),
        expected_evidence=_CONTEXT_EVIDENCE + evidence,
        allowed_evidence=_CONTEXT_EVIDENCE + evidence,
        expected_follow_up_required=follow_up_required,
        expected_structured=True,
        expected_close_count=0,
        expected_classifications=classification,
        appointment_records=appointments,
    )


def system_scenarios() -> tuple[EvaluationCase, ...]:
    """System scenarios. Expected tokens are scripted, not clinical rules."""
    context_allowed = ((FOLLOWUP_TOOL, "allowed"),)
    both_allowed = context_allowed + ((APPOINTMENTS_TOOL, "allowed"),)
    return (
        EvaluationCase(
            id="context-sufficient",
            case_id=PATIENT_CASE,
            replies=(_context(), FinalReply("unknown")),
            expected_tools=(FOLLOWUP_TOOL,),
            expected_status="finish",
            expected_policy=context_allowed,
            expected_evidence=_CONTEXT_EVIDENCE,
            allowed_evidence=_CONTEXT_EVIDENCE,
            expected_follow_up_required="unknown",
            expected_structured=True,
            expected_close_count=0,
        ),
        EvaluationCase(
            id="appointment-required",
            case_id=PATIENT_CASE,
            replies=(_context(), _appointments(), FinalReply("false")),
            expected_tools=(FOLLOWUP_TOOL, APPOINTMENTS_TOOL),
            expected_status="finish",
            expected_policy=both_allowed,
            expected_evidence=_BOTH_EVIDENCE,
            allowed_evidence=_BOTH_EVIDENCE,
            expected_follow_up_required="false",
            expected_structured=True,
            expected_close_count=0,
            expected_classifications=(UPCOMING_CONFIRMED,),
        ),
        EvaluationCase(
            id="empty-appointment-search",
            case_id=PATIENT_CASE,
            replies=(_context(), _appointments(), FinalReply("unknown")),
            expected_tools=(FOLLOWUP_TOOL, APPOINTMENTS_TOOL),
            expected_status="finish",
            expected_policy=both_allowed,
            expected_evidence=_CONTEXT_EVIDENCE,
            allowed_evidence=_CONTEXT_EVIDENCE,
            expected_follow_up_required="unknown",
            expected_structured=True,
            expected_close_count=0,
            fhir="no_appointments",
            expected_classifications=(NONE,),
        ),
        EvaluationCase(
            id="unknown-tool",
            case_id=PATIENT_CASE,
            replies=(ToolReply("unknown_tool", {"case_id": PATIENT_CASE}),),
            expected_tools=(),
            expected_status="denied",
            expected_policy=(("unknown_tool", "denied"),),
            expected_evidence=(),
            allowed_evidence=(),
            expected_follow_up_required="unknown",
            expected_structured=False,
            expected_close_count=0,
        ),
        EvaluationCase(
            id="write-effect-denied",
            case_id=PATIENT_CASE,
            replies=(ToolReply("send_message", {"patient_id": PATIENT_ID, "body": "synthetic"}),),
            expected_tools=(),
            expected_status="denied",
            expected_policy=(("send_message", "denied"),),
            expected_evidence=(),
            allowed_evidence=(),
            expected_follow_up_required="unknown",
            expected_structured=False,
            expected_close_count=0,
        ),
        EvaluationCase(
            id="unavailable-patient",
            case_id=MISSING_CASE,
            replies=(_context(MISSING_CASE),),
            expected_tools=(),
            expected_status="unavailable",
            expected_policy=context_allowed,
            expected_evidence=(),
            allowed_evidence=(),
            expected_follow_up_required="unknown",
            expected_structured=False,
            expected_close_count=0,
            fhir="missing_patient",
        ),
        EvaluationCase(
            id="model-turn-limit",
            case_id=PATIENT_CASE,
            replies=tuple(_context() for _ in range(MAX_MODEL_TURNS)),
            expected_tools=tuple(FOLLOWUP_TOOL for _ in range(MAX_MODEL_TURNS)),
            expected_status="limit",
            expected_policy=tuple((FOLLOWUP_TOOL, "allowed") for _ in range(MAX_MODEL_TURNS)),
            expected_evidence=_CONTEXT_EVIDENCE,
            allowed_evidence=_CONTEXT_EVIDENCE,
            expected_follow_up_required="unknown",
            expected_structured=False,
            expected_close_count=0,
        ),
        EvaluationCase(
            id="close-path",
            case_id=PATIENT_CASE,
            replies=(
                _context(),
                _appointments(),
                UnstructuredReply(),
                FinalReply("unknown"),
            ),
            expected_tools=(FOLLOWUP_TOOL, APPOINTMENTS_TOOL),
            expected_status="finish",
            expected_policy=both_allowed,
            expected_evidence=_BOTH_EVIDENCE,
            allowed_evidence=_BOTH_EVIDENCE,
            expected_follow_up_required="unknown",
            expected_structured=True,
            expected_close_count=1,
            expected_classifications=(UPCOMING_CONFIRMED,),
        ),
        EvaluationCase(
            id="direct-structured-final",
            case_id=PATIENT_CASE,
            replies=(_context(), _appointments(), FinalReply("true")),
            expected_tools=(FOLLOWUP_TOOL, APPOINTMENTS_TOOL),
            expected_status="finish",
            expected_policy=both_allowed,
            expected_evidence=_BOTH_EVIDENCE,
            allowed_evidence=_BOTH_EVIDENCE,
            expected_follow_up_required="true",
            expected_structured=True,
            expected_close_count=0,
            expected_classifications=(UPCOMING_CONFIRMED,),
        ),
        _schedule_case(
            "schedule-none",
            appointments=(),
            classification=(NONE,),
            evidence=(),
            follow_up_required="unknown",
        ),
        _schedule_case(
            "schedule-confirmed",
            appointments=None,
            classification=(UPCOMING_CONFIRMED,),
            evidence=_APPOINTMENT_EVIDENCE,
            follow_up_required="unknown",
        ),
        _schedule_case(
            "schedule-unconfirmed",
            appointments=(
                synthetic_appointment(
                    appointment_id="appointment-synthetic-pending-001",
                    status="pending",
                    start="2027-06-01T15:00:00Z",
                    patient_id=PATIENT_ID,
                ),
            ),
            classification=(UPCOMING_UNCONFIRMED,),
            evidence=((APPOINTMENTS_TOOL, "Appointment/appointment-synthetic-pending-001"),),
            follow_up_required="unknown",
        ),
        _schedule_case(
            "schedule-cancelled",
            appointments=(
                synthetic_appointment(
                    appointment_id="appointment-synthetic-cancelled-001",
                    status="cancelled",
                    start="2027-04-01T15:00:00Z",
                    patient_id=PATIENT_ID,
                ),
            ),
            classification=(CANCELLED,),
            evidence=((APPOINTMENTS_TOOL, "Appointment/appointment-synthetic-cancelled-001"),),
            follow_up_required="unknown",
        ),
        EvaluationCase(
            id="context-no-observations",
            case_id=NO_OBSERVATION_CASE,
            replies=(_context(NO_OBSERVATION_CASE), FinalReply("unknown")),
            expected_tools=(FOLLOWUP_TOOL,),
            expected_status="finish",
            expected_policy=((FOLLOWUP_TOOL, "allowed"),),
            expected_evidence=((FOLLOWUP_TOOL, f"Patient/{NO_OBSERVATION_PATIENT}"),),
            allowed_evidence=((FOLLOWUP_TOOL, f"Patient/{NO_OBSERVATION_PATIENT}"),),
            expected_follow_up_required="unknown",
            expected_structured=True,
            expected_close_count=0,
            fhir="no_observations",
        ),
        EvaluationCase(
            id="observation-read-unavailable",
            case_id=PATIENT_CASE,
            replies=(_context(),),
            expected_tools=(),
            expected_status="unavailable",
            expected_policy=((FOLLOWUP_TOOL, "allowed"),),
            expected_evidence=(),
            allowed_evidence=(),
            expected_follow_up_required="unknown",
            expected_structured=False,
            expected_close_count=0,
            fhir="observation_unavailable",
        ),
        _schedule_case(
            "schedule-past",
            appointments=(
                synthetic_appointment(
                    appointment_id="appointment-synthetic-past-001",
                    status="booked",
                    start="2020-01-15T15:00:00Z",
                    patient_id=PATIENT_ID,
                ),
            ),
            classification=(PAST,),
            evidence=((APPOINTMENTS_TOOL, "Appointment/appointment-synthetic-past-001"),),
            follow_up_required="unknown",
        ),
    )


SYSTEM_SCENARIOS = system_scenarios()
