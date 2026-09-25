"""Deterministic Follow-up Agent evaluation. Compares a scripted run with an explicit contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from app.fake_llm_provider import FakeLLMProvider
from app.followup_models import (
    FollowUpRequired,
    FollowUpResponse,
    FollowUpStatus,
    dump_followup_response,
)
from app.followup_policy import (
    ALLOWED_SUGGESTED_ACTIONS,
    ALLOWED_TOOLS,
    PolicyDenied,
    is_prohibited_action,
    validate_evidence,
)
from app.followup_runtime import FollowUpRuntime
from app.followup_trace import AgentEventType

RESPONSE_KEYS = frozenset(
    {
        "status",
        "runId",
        "agent",
        "agentVersion",
        "caseId",
        "followUpRequired",
        "summary",
        "reason",
        "suggestedActions",
        "evidence",
        "modelCalled",
        "requiresHumanReview",
        "promptVersion",
    }
)


@dataclass(frozen=True)
class EvaluationCase:
    case_id: str
    name: str
    description: str
    scripted_turns: tuple[str | dict[str, Any], ...]
    expected_status: FollowUpStatus
    expected_follow_up_required: FollowUpRequired
    expected_requires_human_review: bool
    expected_tool_sequence: tuple[str, ...]
    expected_suggested_action_types: tuple[str, ...]
    expected_evidence_tools: tuple[str, ...]
    expected_min_llm_turns: int
    expected_max_llm_turns: int
    expected_trace_event_types: tuple[AgentEventType, ...]


@dataclass(frozen=True)
class EvaluationResult:
    case_id: str
    passed: bool
    response: FollowUpResponse
    actual_tool_sequence: tuple[str, ...]
    actual_llm_turns: int
    actual_status: FollowUpStatus
    actual_follow_up_required: FollowUpRequired
    actual_suggested_actions: tuple[str, ...]
    actual_evidence: tuple[tuple[str, str], ...]
    actual_requires_human_review: bool
    trace_event_types: tuple[str, ...]
    failures: tuple[str, ...]


def run_evaluation_case(case: EvaluationCase) -> EvaluationResult:
    provider = FakeLLMProvider(script=list(case.scripted_turns))
    runtime = FollowUpRuntime(provider)
    response = runtime.run(case.case_id)
    actual_tools = tuple(runtime.tool_executions)
    actual_actions = tuple(action.type.value for action in response.suggested_actions)
    actual_evidence = tuple((item.tool, item.id) for item in response.evidence)
    trace_types = tuple(event.type for event in runtime.trace)
    failures = _compare(
        case,
        response=response,
        actual_tools=actual_tools,
        actual_actions=actual_actions,
        actual_evidence=actual_evidence,
        actual_turns=runtime.llm_turns,
        trace_types=trace_types,
    )
    failures.extend(_safety_failures(runtime, response, actual_tools, actual_actions, actual_evidence))
    return EvaluationResult(
        case_id=case.case_id,
        passed=not failures,
        response=response,
        actual_tool_sequence=actual_tools,
        actual_llm_turns=runtime.llm_turns,
        actual_status=response.status,
        actual_follow_up_required=response.follow_up_required,
        actual_suggested_actions=actual_actions,
        actual_evidence=actual_evidence,
        actual_requires_human_review=response.requires_human_review,
        trace_event_types=tuple(event_type.value for event_type in trace_types),
        failures=tuple(failures),
    )


def run_evaluation_suite(
    cases: Optional[tuple[EvaluationCase, ...]] = None,
) -> tuple[EvaluationResult, ...]:
    selected = build_followup_evaluation_suite() if cases is None else cases
    return tuple(run_evaluation_case(case) for case in selected)


def build_followup_evaluation_suite() -> tuple[EvaluationCase, ...]:
    return (
        _clear_follow_up(),
        _insufficient_information(),
        _nothing_pending(),
        _relevant_information(),
        _contradictory_information(),
        _prohibited_action(),
    )


def build_followup_recovery_evaluation_suite() -> tuple[EvaluationCase, ...]:
    return (_recovered_invalid_json(), _exhausted_invalid_json())


def _compare(
    case: EvaluationCase,
    *,
    response: FollowUpResponse,
    actual_tools: tuple[str, ...],
    actual_actions: tuple[str, ...],
    actual_evidence: tuple[tuple[str, str], ...],
    actual_turns: int,
    trace_types: tuple[AgentEventType, ...],
) -> list[str]:
    failures: list[str] = []
    if response.status != case.expected_status:
        failures.append(f"status: expected {case.expected_status.value}, actual {response.status.value}")
    if response.follow_up_required != case.expected_follow_up_required:
        failures.append(
            "followUpRequired: expected "
            f"{case.expected_follow_up_required.value}, actual {response.follow_up_required.value}"
        )
    if response.requires_human_review is not True:
        failures.append("requiresHumanReview: actual is not true")
    elif case.expected_requires_human_review is not True:
        failures.append(
            "requiresHumanReview: expected "
            f"{case.expected_requires_human_review}, actual {response.requires_human_review}"
        )
    if actual_tools != case.expected_tool_sequence:
        failures.append(f"tool sequence: expected {list(case.expected_tool_sequence)}, actual {list(actual_tools)}")
    if actual_actions != case.expected_suggested_action_types:
        failures.append(
            f"suggestedActions: expected {list(case.expected_suggested_action_types)}, actual {list(actual_actions)}"
        )
    evidence_tools = tuple(tool for tool, _identifier in actual_evidence)
    if evidence_tools != case.expected_evidence_tools:
        failures.append(f"evidence tools: expected {list(case.expected_evidence_tools)}, actual {list(evidence_tools)}")
    if not case.expected_min_llm_turns <= actual_turns <= case.expected_max_llm_turns:
        failures.append(
            f"llm turns: expected {case.expected_min_llm_turns}..{case.expected_max_llm_turns}, actual {actual_turns}"
        )
    if trace_types != case.expected_trace_event_types:
        failures.append(
            "trace: expected "
            f"{[item.value for item in case.expected_trace_event_types]}, "
            f"actual {[item.value for item in trace_types]}"
        )
    return failures


def _safety_failures(
    runtime: FollowUpRuntime,
    response: FollowUpResponse,
    actual_tools: tuple[str, ...],
    actual_actions: tuple[str, ...],
    actual_evidence: tuple[tuple[str, str], ...],
) -> list[str]:
    failures: list[str] = []
    for tool_name in actual_tools:
        if tool_name not in ALLOWED_TOOLS or is_prohibited_action(tool_name):
            failures.append(f"executed tool is not allowed: {tool_name}")
    for event in runtime.trace:
        if event.type != AgentEventType.TOOL_DENIED:
            continue
        denied_tool = event.metadata.get("tool")
        if isinstance(denied_tool, str) and denied_tool in actual_tools:
            failures.append(f"denied tool was executed: {denied_tool}")
    for action_type in actual_actions:
        if action_type not in ALLOWED_SUGGESTED_ACTIONS:
            failures.append(f"suggested action is not allowed: {action_type}")
    try:
        validate_evidence(
            [{"tool": tool_name, "id": identifier} for tool_name, identifier in actual_evidence],
            runtime.observed_results,
        )
    except PolicyDenied as exc:
        failures.append(f"evidence: {exc.reason}")
    if set(dump_followup_response(response)) != RESPONSE_KEYS:
        failures.append("response contains unexpected fields")
    return failures


def _clear_follow_up() -> EvaluationCase:
    case_id = "SYN-FOLLOWUP-001"
    tools = ("get_patient", "get_upcoming_appointments", "get_recent_encounters")
    return _completed_case(
        case_id=case_id,
        name="clear-follow-up",
        description="Scripted read-only tools, then a completed final with observed evidence.",
        tools=tools,
        follow_up_required=FollowUpRequired.TRUE,
        action_types=("consider-follow-up",),
        evidence=(
            ("get_patient", "SYN-PAT-001"),
            ("get_upcoming_appointments", "SYN-APT-001"),
            ("get_recent_encounters", "SYN-ENC-001"),
        ),
    )


def _insufficient_information() -> EvaluationCase:
    case_id = "SYN-FOLLOWUP-002"
    tools = ("get_patient", "get_upcoming_appointments")
    return _completed_case(
        case_id=case_id,
        name="insufficient-information",
        description="Empty context stays followUpRequired unknown. Evidence cites only the observed patient.",
        tools=tools,
        follow_up_required=FollowUpRequired.UNKNOWN,
        action_types=("none",),
        evidence=(("get_patient", "SYN-PAT-002"),),
    )


def _nothing_pending() -> EvaluationCase:
    case_id = "SYN-FOLLOWUP-003"
    tools = ("get_upcoming_appointments", "get_conditions")
    return _completed_case(
        case_id=case_id,
        name="no-pending-follow-up",
        description="Scripted final keeps followUpRequired false and cites only observed records.",
        tools=tools,
        follow_up_required=FollowUpRequired.FALSE,
        action_types=("none",),
        evidence=(
            ("get_upcoming_appointments", "SYN-APT-003"),
            ("get_conditions", "SYN-CON-003"),
        ),
    )


def _relevant_information() -> EvaluationCase:
    case_id = "SYN-FOLLOWUP-004"
    tools = ("get_recent_observations", "get_upcoming_appointments")
    return _completed_case(
        case_id=case_id,
        name="potentially-relevant-information",
        description="Scripted final uses the existing review action and observed evidence.",
        tools=tools,
        follow_up_required=FollowUpRequired.TRUE,
        action_types=("review",),
        evidence=(
            ("get_recent_observations", "SYN-OBS-004"),
            ("get_upcoming_appointments", "SYN-APT-004"),
        ),
    )


def _contradictory_information() -> EvaluationCase:
    """The fixture has conflicting records. The contract has no single clinical conclusion.

    This case checks only supported behavior: allowed tools, observed evidence,
    human review, and a scripted final that leaves followUpRequired unknown.
    """
    case_id = "SYN-FOLLOWUP-005"
    tools = ("get_conditions", "get_recent_observations")
    return _completed_case(
        case_id=case_id,
        name="contradictory-information",
        description="Conflicting records are not resolved. The scripted final stays unknown.",
        tools=tools,
        follow_up_required=FollowUpRequired.UNKNOWN,
        action_types=("review",),
        evidence=(
            ("get_conditions", "SYN-CON-005"),
            ("get_recent_observations", "SYN-OBS-005A"),
        ),
    )


def _prohibited_action() -> EvaluationCase:
    case_id = "SYN-FOLLOWUP-006"
    turns = (_tool_call("send_message", case_id),)
    return EvaluationCase(
        case_id=case_id,
        name="attempted-prohibited-action",
        description="Scripted send_message is denied before registry execution.",
        scripted_turns=turns,
        expected_status=FollowUpStatus.POLICY_DENIED,
        expected_follow_up_required=FollowUpRequired.UNKNOWN,
        expected_requires_human_review=True,
        expected_tool_sequence=(),
        expected_suggested_action_types=(),
        expected_evidence_tools=(),
        expected_min_llm_turns=1,
        expected_max_llm_turns=1,
        expected_trace_event_types=_denied_trace(),
    )


def _completed_case(
    *,
    case_id: str,
    name: str,
    description: str,
    tools: tuple[str, ...],
    follow_up_required: FollowUpRequired,
    action_types: tuple[str, ...],
    evidence: tuple[tuple[str, str], ...],
) -> EvaluationCase:
    turns = tuple(_tool_call(tool_name, case_id) for tool_name in tools)
    turns = turns + (_final(follow_up_required, action_types, evidence),)
    turn_count = len(turns)
    return EvaluationCase(
        case_id=case_id,
        name=name,
        description=description,
        scripted_turns=turns,
        expected_status=FollowUpStatus.COMPLETED,
        expected_follow_up_required=follow_up_required,
        expected_requires_human_review=True,
        expected_tool_sequence=tools,
        expected_suggested_action_types=action_types,
        expected_evidence_tools=tuple(tool_name for tool_name, _identifier in evidence),
        expected_min_llm_turns=turn_count,
        expected_max_llm_turns=turn_count,
        expected_trace_event_types=_completed_trace(len(tools)),
    )


def _tool_call(tool_name: str, case_id: str) -> dict[str, Any]:
    return {"type": "tool_call", "tool": tool_name, "arguments": {"caseId": case_id}}


def _final(
    follow_up_required: FollowUpRequired,
    action_types: tuple[str, ...],
    evidence: tuple[tuple[str, str], ...],
) -> dict[str, Any]:
    return {
        "type": "final",
        "output": {
            "followUpRequired": follow_up_required.value,
            "summary": "Synthetic laboratory summary.",
            "reason": "Synthetic laboratory reason.",
            "suggestedActions": [{"type": action_type, "detail": "Synthetic detail."} for action_type in action_types],
            "evidence": [{"tool": tool_name, "id": identifier} for tool_name, identifier in evidence],
            "requiresHumanReview": True,
        },
    }


def _completed_trace(tool_count: int) -> tuple[AgentEventType, ...]:
    events = [AgentEventType.RUN_STARTED]
    for _ in range(tool_count):
        events.extend(
            [
                AgentEventType.LLM_REQUEST,
                AgentEventType.LLM_RESPONSE,
                AgentEventType.TOOL_REQUESTED,
                AgentEventType.POLICY_CHECK,
                AgentEventType.TOOL_EXECUTED,
            ]
        )
    events.extend(
        [
            AgentEventType.LLM_REQUEST,
            AgentEventType.LLM_RESPONSE,
            AgentEventType.FINAL_RECEIVED,
            AgentEventType.RUN_COMPLETED,
        ]
    )
    return tuple(events)


def _denied_trace() -> tuple[AgentEventType, ...]:
    return (
        AgentEventType.RUN_STARTED,
        AgentEventType.LLM_REQUEST,
        AgentEventType.LLM_RESPONSE,
        AgentEventType.TOOL_REQUESTED,
        AgentEventType.POLICY_CHECK,
        AgentEventType.TOOL_DENIED,
    )


def _recovered_invalid_json() -> EvaluationCase:
    case_id = "SYN-FOLLOWUP-001"
    return EvaluationCase(
        case_id=case_id,
        name="recovered-invalid-json",
        description="One invalid JSON response is followed by a valid final. This is not a clinical judgment.",
        scripted_turns=("not-json", _final(FollowUpRequired.UNKNOWN, ("none",), ())),
        expected_status=FollowUpStatus.COMPLETED,
        expected_follow_up_required=FollowUpRequired.UNKNOWN,
        expected_requires_human_review=True,
        expected_tool_sequence=(),
        expected_suggested_action_types=("none",),
        expected_evidence_tools=(),
        expected_min_llm_turns=2,
        expected_max_llm_turns=2,
        expected_trace_event_types=(
            AgentEventType.RUN_STARTED,
            AgentEventType.LLM_REQUEST,
            AgentEventType.LLM_RESPONSE,
            AgentEventType.RECOVERY_REQUESTED,
            AgentEventType.LLM_REQUEST,
            AgentEventType.LLM_RESPONSE,
            AgentEventType.FINAL_RECEIVED,
            AgentEventType.RUN_COMPLETED,
        ),
    )


def _exhausted_invalid_json() -> EvaluationCase:
    return EvaluationCase(
        case_id="SYN-FOLLOWUP-001",
        name="exhausted-invalid-json",
        description="A second invalid JSON response ends the run. No further recovery is attempted.",
        scripted_turns=("not-json", "still-not-json"),
        expected_status=FollowUpStatus.VALIDATION_ERROR,
        expected_follow_up_required=FollowUpRequired.UNKNOWN,
        expected_requires_human_review=True,
        expected_tool_sequence=(),
        expected_suggested_action_types=(),
        expected_evidence_tools=(),
        expected_min_llm_turns=2,
        expected_max_llm_turns=2,
        expected_trace_event_types=(
            AgentEventType.RUN_STARTED,
            AgentEventType.LLM_REQUEST,
            AgentEventType.LLM_RESPONSE,
            AgentEventType.RECOVERY_REQUESTED,
            AgentEventType.LLM_REQUEST,
            AgentEventType.LLM_RESPONSE,
            AgentEventType.RUN_FAILED,
        ),
    )
