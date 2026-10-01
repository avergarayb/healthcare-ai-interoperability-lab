"""Consolidated follow-up workflow.

The application calls FollowUpWorkflow.run. The HTTP follow-up endpoint
calls that method. This module hides the LangGraph loop. Policy, audit, FHIR,
HTTP, authentication, and the HTTP contract stay outside the graph.

```text
HTTP/Application
        |
        v
FollowUpWorkflow
        |
        +-- authorized read scope
        +-- mandatory Patient/Encounter/Observation/Appointment acquisition
        +-- deterministic protocol evaluation
        |
        v
     LangGraph
        |
        +-- agent
        +-- routing
        +-- ToolNode
        +-- state
        |
        v
Clinical Tools
        |
        v
FHIRAdapter
        |
        v
FHIRTransport
        |
        v
FHIRReadClient
        |
        v
HAPI FHIR
```

The application still owns policy, authorization, audit, security, HTTP,
authentication, validation, FHIR access, contracts, production observability,
human review, and PHI protection. Those are not LangGraph nodes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Literal

from app.langgraph_fhir_client import (
    ReadClientError,
    evaluate_tool_policy,
    record_policy_audit,
)
from app.langgraph_fhir_followup import PostConsultationContextReader, UNAVAILABLE_ANSWER
from app.langgraph_gemini_fhir_followup import (
    MAX_MODEL_TURNS,
    build_gemini_fhir_followup,
)
from app.followup_review import FollowUpReviewCase
from app.post_consultation_review import (
    ProtocolEvaluationStatus,
    ProtocolReviewResult,
    evaluate_post_consultation_review,
    not_evaluated_protocol,
)


LANGGRAPH_RESPONSIBILITIES = (
    "workflow state",
    "agent and tool loop",
    "routing",
    "tool execution",
    "turn limit",
    "messages between the model and the tools",
)
FollowUpDecision = Literal["true", "false", "unknown"]
_FOLLOW_UP_DECISIONS = frozenset({"true", "false", "unknown"})


APPLICATION_RESPONSIBILITIES = (
    "policy",
    "authorization",
    "audit",
    "security",
    "http",
    "authentication",
    "validation",
    "fhir",
    "contracts",
    "production observability",
    "human review",
    "phi protection",
)


@dataclass(frozen=True)
class FollowUpWorkflowResult:
    """Application view of one run. It carries no model message objects."""

    case_id: str
    status: str
    final_answer: str
    patient: dict[str, Any] | None
    observations: list[dict[str, Any]]
    evidence: list[dict[str, Any]]
    tools_used: list[str]
    turns: int
    run_id: str
    follow_up_required: FollowUpDecision
    context_patient: str = "not_read"
    context_observation: str = "not_read"
    schedule_check: str = "not_checked"
    schedule_classifications: tuple[str, ...] = ()
    schedule_appointments: tuple[tuple[str, str], ...] = ()
    protocol: ProtocolReviewResult = field(default_factory=not_evaluated_protocol)
    encounter_collection: str = "not_read"
    observation_collection: str = "not_read"
    appointment_collection: str = "not_read"
    protocol_encounters: tuple[dict[str, Any], ...] = ()
    review_case: FollowUpReviewCase | None = None


class FollowUpWorkflow:
    """Run the existing follow-up graph behind an application method."""

    def __init__(
        self,
        *,
        model: Callable[..., Any],
        sink,
        fhir_client,
        policy: Callable[..., Any] = evaluate_tool_policy,
        audit: Callable[..., Any] = record_policy_audit,
        clock: Callable[[], str],
        run_id: str,
        now: Callable[[], datetime] | None = None,
        ensure_review_case: Callable[
            [str, ProtocolReviewResult], FollowUpReviewCase | None
        ]
        | None = None,
    ) -> None:
        self.model = model
        self.sink = sink
        self.fhir_client = fhir_client
        self.policy = policy
        self.audit = audit
        self.clock = clock
        self.run_id = run_id
        self.ensure_review_case = ensure_review_case
        self._engine = build_gemini_fhir_followup(
            fhir_client,
            sink,
            model,
            clock=clock,
            run_id=run_id,
            policy=policy,
            audit=audit,
            now=now,
        )
        self._protocol_reader = PostConsultationContextReader(self._engine.adapter)

    def run(self, case_id: str) -> FollowUpWorkflowResult:
        """Execute one case and return the application result."""
        adapter = self._engine.adapter
        with adapter.bind_read(case_id):
            try:
                snapshot = self._protocol_reader.read(case_id)
            except ReadClientError:
                snapshot = adapter.ledger.protocol_snapshot()
            protocol = evaluate_post_consultation_review(snapshot)
            if protocol.evaluation_status is ProtocolEvaluationStatus.UNAVAILABLE:
                return self._unavailable_result(case_id, protocol)
            review_case = (
                self.ensure_review_case(case_id, protocol)
                if self.ensure_review_case is not None
                else None
            )
            state = self._engine.invoke(case_id)
            patient = state["patient"]
            ledger = adapter.ledger
            return FollowUpWorkflowResult(
                case_id=state["case_id"],
                status=state["decision"],
                final_answer=state["final_answer"] or "",
                patient=dict(patient) if isinstance(patient, dict) else None,
                observations=[dict(item) for item in state["observations"]],
                evidence=[dict(item) for item in state["evidence"]],
                tools_used=list(state["tools_used"]),
                turns=int(state["turn"]),
                run_id=self.run_id,
                follow_up_required=_explicit_follow_up_required(state),
                context_patient=state["context_patient"],
                context_observation=state["context_observation"],
                schedule_check=state["schedule_check"],
                schedule_classifications=state["schedule_classifications"],
                schedule_appointments=state["schedule_appointments"],
                protocol=protocol,
                encounter_collection=ledger.encounter_collection.value,
                observation_collection=ledger.observation_collection.value,
                appointment_collection=ledger.appointment_collection.value,
                protocol_encounters=tuple(dict(item) for item in ledger.encounters),
                review_case=review_case,
            )

    def _unavailable_result(
        self,
        case_id: str,
        protocol: ProtocolReviewResult,
    ) -> FollowUpWorkflowResult:
        ledger = self._engine.adapter.ledger
        patient = ledger.patient_resource
        return FollowUpWorkflowResult(
            case_id=case_id,
            status="unavailable",
            final_answer=UNAVAILABLE_ANSWER,
            patient=dict(patient) if isinstance(patient, dict) else None,
            observations=[dict(item) for item in (ledger.observations or [])],
            evidence=[],
            tools_used=[],
            turns=0,
            run_id=self.run_id,
            follow_up_required="unknown",
            context_patient=ledger.patient,
            context_observation=ledger.observation,
            schedule_check=ledger.schedule_check,
            schedule_classifications=ledger.classifications,
            schedule_appointments=ledger.appointments,
            protocol=protocol,
            encounter_collection=ledger.encounter_collection.value,
            observation_collection=ledger.observation_collection.value,
            appointment_collection=ledger.appointment_collection.value,
            protocol_encounters=tuple(dict(item) for item in ledger.encounters),
        )


def build_live_followup_workflow(
    sink,
    *,
    clock: Callable[[], str],
    run_id: str,
    base_url: str | None = None,
    policy: Callable[..., Any] = evaluate_tool_policy,
    audit: Callable[..., Any] = record_policy_audit,
    ensure_review_case: Callable[
        [str, ProtocolReviewResult], FollowUpReviewCase | None
    ]
    | None = None,
) -> FollowUpWorkflow:
    """Compose the live model and the live read client outside the workflow class."""
    from app.langgraph_fhir_hapi import HapiReadClient
    from app.langgraph_gemini_fhir_followup import gemini_followup_message

    return FollowUpWorkflow(
        model=gemini_followup_message,
        sink=sink,
        fhir_client=HapiReadClient(base_url),
        policy=policy,
        audit=audit,
        clock=clock,
        run_id=run_id,
        ensure_review_case=ensure_review_case,
    )


def _explicit_follow_up_required(state: dict[str, Any]) -> FollowUpDecision:
    """Read a structured decision. Free text, the patient, and observations do not count."""
    for message in reversed(state.get("messages") or []):
        if type(message).__name__ != "AIMessage" or getattr(message, "tool_calls", None):
            continue
        explicit = (getattr(message, "additional_kwargs", None) or {}).get("follow_up_required")
        if explicit in _FOLLOW_UP_DECISIONS:
            return explicit
        return "unknown"
    return "unknown"


__all__ = [
    "APPLICATION_RESPONSIBILITIES",
    "LANGGRAPH_RESPONSIBILITIES",
    "MAX_MODEL_TURNS",
    "FollowUpDecision",
    "FollowUpWorkflow",
    "FollowUpWorkflowResult",
    "build_live_followup_workflow",
]
