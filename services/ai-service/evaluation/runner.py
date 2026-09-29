"""Run EvaluationCase against FollowUpWorkflow and score system behavior."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone

from langchain_core.messages import AIMessage

from app.langgraph_fhir_client import (
    BOUNDARY_EVENTS,
    PATIENT_ID,
    InMemoryAuditSink,
    PreparedReadClient,
    clear_boundary_events,
)
from app.langgraph_followup_workflow import FollowUpWorkflow
from evaluation.cases import (
    NO_OBSERVATION_PATIENT,
    EvaluationCase,
    FinalReply,
    Reply,
    ToolReply,
    UnstructuredReply,
)


_VALID_DECISIONS = frozenset({"true", "false", "unknown"})


@dataclass(frozen=True)
class EvaluationMetrics:
    """Boolean and count checks. Later suites can sum the counts."""

    tool_sequence_exact_match: bool
    unexpected_tool_count: int
    missing_tool_count: int
    denied_tool_count: int
    tool_execution_count: int
    expected_evidence_present: bool
    unexpected_evidence_count: int
    evidence_tool_matches_source: bool
    structured_decision_present: bool
    follow_up_required_exact_match: bool
    valid_follow_up_required: bool
    expected_policy_decisions: bool
    unexpected_allowed_tool: bool
    denied_tool_not_executed: bool
    model_turn_count: int
    close_used: bool
    termination_status: str
    within_turn_limit: bool


@dataclass(frozen=True)
class EvaluationObservation:
    """What one productive run did. It keeps ids and decisions, not clinical text."""

    tool_sequence: tuple[str, ...]
    policy: tuple[tuple[str, str], ...]
    evidence: tuple[tuple[str, str], ...]
    follow_up_required: str
    structured_decision_present: bool
    status: str
    model_turns: int
    close_count: int
    fhir_calls: tuple[str, ...]
    executed_effects: tuple[str, ...]
    classifications: tuple[str, ...]


@dataclass(frozen=True)
class EvaluationResult:
    evaluation_case_id: str
    case_id: str
    passed: bool
    tool_sequence: tuple[str, ...]
    expected_tool_sequence: tuple[str, ...]
    policy_decisions: tuple[tuple[str, str], ...]
    evidence_ids: tuple[tuple[str, str], ...]
    follow_up_required: str
    status: str
    model_turns: int
    close_used: bool
    classifications: tuple[str, ...]
    failures: tuple[str, ...]
    metrics: EvaluationMetrics


class ScriptedModel:
    """Return prepared messages. This is not a second agent."""

    def __init__(self, replies: list[AIMessage]) -> None:
        self._replies = list(replies)
        self.produced: list[AIMessage] = []

    def __call__(self, messages: list[object]) -> AIMessage:
        del messages
        if not self._replies:
            raise RuntimeError("scripted model has no reply")
        message = self._replies.pop(0)
        self.produced.append(message)
        return message


def _message(step: Reply, index: int, case_id: str) -> AIMessage:
    if isinstance(step, ToolReply):
        arguments = step.arguments if step.arguments is not None else {"case_id": case_id}
        return AIMessage(
            content="",
            tool_calls=[
                {
                    "name": step.name,
                    "args": arguments,
                    "id": f"call-{index}",
                    "type": "tool_call",
                }
            ],
        )
    if isinstance(step, FinalReply):
        message = AIMessage(content=step.text)
        message.additional_kwargs["follow_up_required"] = step.follow_up_required
        return message
    if isinstance(step, UnstructuredReply):
        return AIMessage(content=step.text)
    raise TypeError("unsupported evaluation reply")


def _structured_present(messages: list[AIMessage]) -> bool:
    for message in reversed(messages):
        if message.tool_calls:
            continue
        token = (message.additional_kwargs or {}).get("follow_up_required")
        return token in _VALID_DECISIONS
    return False


def _flatten_evidence(evidence: list[dict]) -> tuple[tuple[str, str], ...]:
    rows: list[tuple[str, str]] = []
    for entry in evidence:
        tool = entry.get("tool")
        resources = entry.get("resources")
        if not isinstance(tool, str) or not isinstance(resources, list):
            continue
        for reference in resources:
            if isinstance(reference, str) and reference:
                rows.append((tool, reference))
    return tuple(rows)


def observe(case: EvaluationCase) -> EvaluationObservation:
    """Execute one case on the productive workflow."""
    clear_boundary_events()
    model = ScriptedModel([_message(step, index, case.case_id) for index, step in enumerate(case.replies, start=1)])
    if case.appointment_records is not None:
        appointment_records = [dict(item) for item in case.appointment_records]
    elif case.fhir == "no_appointments":
        appointment_records = []
    else:
        appointment_records = None
    if case.fhir == "no_observations":
        client = PreparedReadClient(
            case_id=case.case_id,
            patient_id=NO_OBSERVATION_PATIENT,
            observations=[],
            appointments=[],
        )
    elif case.fhir == "observation_unavailable":
        client = PreparedReadClient(fail_observation_read=True)
    else:
        client = PreparedReadClient(appointments=appointment_records)
    sink = InMemoryAuditSink()
    workflow = FollowUpWorkflow(
        model=model,
        sink=sink,
        fhir_client=client,
        clock=lambda: "2026-09-28T00:00:00Z",
        run_id=f"eval-{case.id}",
        now=lambda: datetime(2026, 9, 28, tzinfo=timezone.utc),
    )
    result = workflow.run(case.case_id)
    executed = tuple(
        event.removeprefix("execute:") for event in BOUNDARY_EVENTS if event.startswith("execute:")
    )
    # model_calls still counts a request when an unavailable read replaces workflow.turns.
    return EvaluationObservation(
        tool_sequence=tuple(result.tools_used),
        policy=tuple((event.tool_name, event.decision) for event in sink.events),
        evidence=_flatten_evidence(result.evidence),
        follow_up_required=result.follow_up_required,
        structured_decision_present=_structured_present(model.produced),
        status=result.status,
        model_turns=workflow._engine.model_calls,
        close_count=workflow._engine.trace.count("close"),
        fhir_calls=tuple(client.calls),
        executed_effects=executed,
        classifications=tuple(workflow._engine.adapter.appointment_classifications),
    )


def _tool_counts(actual: tuple[str, ...], expected: tuple[str, ...]) -> tuple[int, int]:
    actual_counts = Counter(actual)
    expected_counts = Counter(expected)
    missing = sum((expected_counts - actual_counts).values())
    unexpected = sum((actual_counts - expected_counts).values())
    return missing, unexpected


def score(case: EvaluationCase, observation: EvaluationObservation) -> EvaluationResult:
    """Compare one observation with the case. This function does not call the model."""
    missing_tools, unexpected_tools = _tool_counts(observation.tool_sequence, case.expected_tools)
    exact_tools = observation.tool_sequence == case.expected_tools
    denied = tuple(name for name, decision in observation.policy if decision == "denied")
    denied_executed = [
        name for name in denied if name in observation.tool_sequence or name in observation.executed_effects
    ]
    expected_allowed = {name for name, decision in case.expected_policy if decision == "allowed"}
    actual_allowed = [name for name, decision in observation.policy if decision == "allowed"]
    unexpected_allowed = [name for name in actual_allowed if name not in expected_allowed]
    allowed_evidence = set(case.allowed_evidence)
    unexpected_evidence = [pair for pair in observation.evidence if pair not in allowed_evidence]
    expected_present = all(pair in observation.evidence for pair in case.expected_evidence)
    evidence_tools_ok = all(tool in observation.tool_sequence for tool, _reference in observation.evidence)
    valid_token = observation.follow_up_required in _VALID_DECISIONS
    token_match = observation.follow_up_required == case.expected_follow_up_required
    policy_match = observation.policy == case.expected_policy
    within_turns = observation.model_turns <= case.max_model_turns
    metrics = EvaluationMetrics(
        tool_sequence_exact_match=exact_tools,
        unexpected_tool_count=unexpected_tools,
        missing_tool_count=missing_tools,
        denied_tool_count=len(denied),
        tool_execution_count=len(observation.tool_sequence),
        expected_evidence_present=expected_present,
        unexpected_evidence_count=len(unexpected_evidence),
        evidence_tool_matches_source=evidence_tools_ok,
        structured_decision_present=observation.structured_decision_present,
        follow_up_required_exact_match=token_match,
        valid_follow_up_required=valid_token,
        expected_policy_decisions=policy_match,
        unexpected_allowed_tool=bool(unexpected_allowed),
        denied_tool_not_executed=not denied_executed,
        model_turn_count=observation.model_turns,
        close_used=observation.close_count > 0,
        termination_status=observation.status,
        within_turn_limit=within_turns,
    )
    failures: list[str] = []
    if not exact_tools:
        failures.append("tool sequence mismatch")
    if missing_tools:
        failures.append("missing tool")
    if unexpected_tools:
        failures.append("unexpected tool")
    if not expected_present:
        failures.append("missing evidence")
    if unexpected_evidence:
        failures.append("unexpected evidence")
    if not evidence_tools_ok:
        failures.append("evidence tool was not executed")
    if observation.structured_decision_present != case.expected_structured:
        failures.append("structured decision mismatch")
    if not token_match:
        failures.append("follow_up_required mismatch")
    if not valid_token:
        failures.append("invalid follow_up_required")
    if not policy_match:
        failures.append("policy mismatch")
    if unexpected_allowed:
        failures.append("unexpected allowed tool")
    if denied_executed:
        failures.append("denied tool was executed")
    if observation.status != case.expected_status:
        failures.append("status mismatch")
    if observation.close_count != case.expected_close_count:
        failures.append("close count mismatch")
    if not within_turns:
        failures.append("model turns exceed limit")
    if case.fhir == "missing_patient":
        if any(f"Patient/{PATIENT_ID}" in path or path.startswith("Appointment") for path in observation.fhir_calls):
            failures.append("patient fallback")
    if case.expected_status == "denied" and observation.fhir_calls:
        failures.append("denied tool called fhir")
    if (
        case.expected_classifications is not None
        and observation.classifications != case.expected_classifications
    ):
        failures.append("appointment classification mismatch")
    return EvaluationResult(
        evaluation_case_id=case.id,
        case_id=case.case_id,
        passed=not failures,
        tool_sequence=observation.tool_sequence,
        expected_tool_sequence=case.expected_tools,
        policy_decisions=observation.policy,
        evidence_ids=observation.evidence,
        follow_up_required=observation.follow_up_required,
        status=observation.status,
        model_turns=observation.model_turns,
        close_used=observation.close_count > 0,
        classifications=observation.classifications,
        failures=tuple(failures),
        metrics=metrics,
    )


def run_case(case: EvaluationCase) -> EvaluationResult:
    return score(case, observe(case))


def run_suite(cases: tuple[EvaluationCase, ...] | None = None) -> tuple[EvaluationResult, ...]:
    from evaluation.cases import SYSTEM_SCENARIOS

    selected = SYSTEM_SCENARIOS if cases is None else cases
    return tuple(run_case(case) for case in selected)
