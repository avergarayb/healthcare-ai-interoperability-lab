from __future__ import annotations

import inspect
from dataclasses import replace

import pytest

from app.followup_evaluation import (
    build_followup_evaluation_suite,
    build_followup_recovery_evaluation_suite,
    run_evaluation_case,
    run_evaluation_suite,
)
from app.followup_models import CASE_IDS, FollowUpRequired, FollowUpStatus
from app.followup_trace import AgentEventType


def test_evaluation_case_is_explicit():
    case = build_followup_evaluation_suite()[0]
    assert case.case_id == "SYN-FOLLOWUP-001"
    assert case.name == "clear-follow-up"
    assert case.scripted_turns
    assert case.expected_status == FollowUpStatus.COMPLETED
    assert case.expected_follow_up_required == FollowUpRequired.TRUE
    assert case.expected_requires_human_review is True
    assert case.expected_tool_sequence == (
        "get_patient",
        "get_upcoming_appointments",
        "get_recent_encounters",
    )
    assert case.expected_min_llm_turns == case.expected_max_llm_turns == 4


def test_successful_case_reports_expected_against_actual():
    result = run_evaluation_case(build_followup_evaluation_suite()[0])
    assert result.passed, result.failures
    assert result.actual_status == FollowUpStatus.COMPLETED
    assert result.actual_tool_sequence == (
        "get_patient",
        "get_upcoming_appointments",
        "get_recent_encounters",
    )
    assert result.actual_llm_turns == 4
    assert result.actual_requires_human_review is True
    assert result.failures == ()


def test_wrong_status_is_reported():
    case = replace(build_followup_evaluation_suite()[0], expected_status=FollowUpStatus.POLICY_DENIED)
    result = run_evaluation_case(case)
    assert result.passed is False
    assert any(item.startswith("status:") for item in result.failures)


def test_wrong_follow_up_required_is_reported():
    case = replace(
        build_followup_evaluation_suite()[0],
        expected_follow_up_required=FollowUpRequired.FALSE,
    )
    result = run_evaluation_case(case)
    assert result.passed is False
    assert any(item.startswith("followUpRequired:") for item in result.failures)


def test_wrong_tool_sequence_is_reported():
    case = replace(
        build_followup_evaluation_suite()[0],
        expected_tool_sequence=("get_recent_encounters", "get_patient", "get_upcoming_appointments"),
    )
    result = run_evaluation_case(case)
    assert result.passed is False
    assert any(item.startswith("tool sequence:") for item in result.failures)


def test_too_many_llm_turns_are_reported():
    case = replace(
        build_followup_evaluation_suite()[0],
        expected_min_llm_turns=1,
        expected_max_llm_turns=1,
    )
    result = run_evaluation_case(case)
    assert result.passed is False
    assert any(item.startswith("llm turns:") for item in result.failures)
    assert result.actual_llm_turns == 4


def test_wrong_suggested_action_is_reported():
    case = replace(
        build_followup_evaluation_suite()[0],
        expected_suggested_action_types=("none",),
    )
    result = run_evaluation_case(case)
    assert result.passed is False
    assert any(item.startswith("suggestedActions:") for item in result.failures)


def test_wrong_evidence_tools_are_reported():
    case = replace(
        build_followup_evaluation_suite()[0],
        expected_evidence_tools=("get_medications",),
    )
    result = run_evaluation_case(case)
    assert result.passed is False
    assert any(item.startswith("evidence tools:") for item in result.failures)


def test_human_review_must_stay_true():
    case = replace(build_followup_evaluation_suite()[0], expected_requires_human_review=False)
    result = run_evaluation_case(case)
    assert result.passed is False
    assert result.actual_requires_human_review is True
    assert any(item.startswith("requiresHumanReview:") for item in result.failures)


def test_allowed_tool_trace_order():
    result = run_evaluation_case(build_followup_evaluation_suite()[0])
    assert result.trace_event_types[:6] == (
        AgentEventType.RUN_STARTED.value,
        AgentEventType.LLM_REQUEST.value,
        AgentEventType.LLM_RESPONSE.value,
        AgentEventType.TOOL_REQUESTED.value,
        AgentEventType.POLICY_CHECK.value,
        AgentEventType.TOOL_EXECUTED.value,
    )
    assert result.trace_event_types[-2:] == (
        AgentEventType.FINAL_RECEIVED.value,
        AgentEventType.RUN_COMPLETED.value,
    )


def test_denied_tool_trace_does_not_execute():
    result = run_evaluation_case(build_followup_evaluation_suite()[5])
    assert result.passed, result.failures
    assert result.actual_status == FollowUpStatus.POLICY_DENIED
    assert result.actual_tool_sequence == ()
    assert AgentEventType.TOOL_EXECUTED.value not in result.trace_event_types
    assert result.trace_event_types[-3:] == (
        AgentEventType.TOOL_REQUESTED.value,
        AgentEventType.POLICY_CHECK.value,
        AgentEventType.TOOL_DENIED.value,
    )


def test_suite_contains_exactly_the_six_fixtures():
    suite = build_followup_evaluation_suite()
    assert tuple(case.case_id for case in suite) == CASE_IDS
    assert len(suite) == 6


def test_recovery_evaluation_cases_pass_and_stay_outside_the_six():
    suite = build_followup_recovery_evaluation_suite()
    assert len(suite) == 2
    assert {case.case_id for case in suite} <= set(CASE_IDS)
    results = run_evaluation_suite(suite)
    assert [result.passed for result in results] == [True, True]


@pytest.mark.parametrize("case", build_followup_evaluation_suite(), ids=lambda case: case.case_id)
def test_each_suite_case_passes(case):
    result = run_evaluation_case(case)
    assert result.passed, result.failures
    assert result.response.requires_human_review is True


def test_suite_runner_passes_without_gemini():
    import app.followup_evaluation as evaluation

    source = inspect.getsource(evaluation)
    assert "GeminiProvider" not in source
    assert "langgraph" not in source.lower()
    results = run_evaluation_suite()
    assert len(results) == 6
    assert all(result.passed for result in results)


def test_evaluation_is_deterministic():
    first = run_evaluation_suite()
    second = run_evaluation_suite()
    assert [_projection(result) for result in first] == [_projection(result) for result in second]


def _projection(result):
    return (
        result.case_id,
        result.passed,
        result.failures,
        result.actual_tool_sequence,
        result.actual_llm_turns,
        result.actual_status,
        result.actual_follow_up_required,
        result.actual_suggested_actions,
        result.actual_evidence,
        result.actual_requires_human_review,
        result.trace_event_types,
        result.response.follow_up_required,
        result.response.summary,
    )
