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

from dataclasses import dataclass
from typing import Any, Callable, Literal

from app.langgraph_fhir_client import (
    evaluate_tool_policy,
    record_policy_audit,
)
from app.langgraph_gemini_fhir_followup import (
    MAX_MODEL_TURNS,
    build_gemini_fhir_followup,
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


class FollowUpWorkflow:
    """Run the existing follow-up graph behind an application method."""

    def __init__(
        self,
        *,
        model: Callable[..., Any],
        sink,
        fhir_client,
        policy: Callable[[str], Any] = evaluate_tool_policy,
        audit: Callable[..., Any] = record_policy_audit,
        clock: Callable[[], str],
        run_id: str,
    ) -> None:
        self.model = model
        self.sink = sink
        self.fhir_client = fhir_client
        self.policy = policy
        self.audit = audit
        self.clock = clock
        self.run_id = run_id
        self._engine = build_gemini_fhir_followup(
            fhir_client,
            sink,
            model,
            clock=clock,
            run_id=run_id,
            policy=policy,
            audit=audit,
        )

    def run(self, case_id: str) -> FollowUpWorkflowResult:
        """Execute one case and return the application result."""
        state = self._engine.invoke(case_id)
        patient = state["patient"]
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
        )


def build_live_followup_workflow(
    sink,
    *,
    clock: Callable[[], str],
    run_id: str,
    base_url: str | None = None,
    policy: Callable[[str], Any] = evaluate_tool_policy,
    audit: Callable[..., Any] = record_policy_audit,
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
