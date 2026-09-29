"""System-behavior scenarios for the productive follow-up workflow."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from app.langgraph_fhir_client import APPOINTMENTS_TOOL, FOLLOWUP_TOOL
from app.langgraph_fhir_followup import CANCELLED, NONE, PAST, UPCOMING_CONFIRMED, UPCOMING_UNCONFIRMED
from app.langgraph_gemini_fhir_followup import MAX_MODEL_TURNS
from evaluation.cases import SYSTEM_SCENARIOS
from evaluation.report import format_report
from evaluation.runner import observe, run_suite, score


APP = Path(__file__).resolve().parents[1] / "app"


def test_system_scenarios_pass_without_inferring_the_token():
    results = run_suite()
    by_id = {result.evaluation_case_id: result for result in results}
    report = format_report(results)
    assert len(results) == 14
    assert all(result.passed for result in results)
    assert report.splitlines()[2:5] == ["14 cases", "14 passed", "0 failed"]
    context = by_id["context-sufficient"]
    assert context.tool_sequence == (FOLLOWUP_TOOL,)
    assert APPOINTMENTS_TOOL not in context.tool_sequence
    assert context.metrics.tool_sequence_exact_match is True
    assert context.metrics.structured_decision_present is True
    assert context.close_used is False
    appointment = by_id["appointment-required"]
    assert appointment.tool_sequence == (FOLLOWUP_TOOL, APPOINTMENTS_TOOL)
    assert appointment.policy_decisions == (
        (FOLLOWUP_TOOL, "allowed"),
        (APPOINTMENTS_TOOL, "allowed"),
    )
    assert any(reference.startswith("Appointment/") for _tool, reference in appointment.evidence_ids)
    empty = by_id["empty-appointment-search"]
    assert empty.tool_sequence == (FOLLOWUP_TOOL, APPOINTMENTS_TOOL)
    assert not any(reference.startswith("Appointment/") for _tool, reference in empty.evidence_ids)
    assert by_id["unknown-tool"].status == "denied"
    assert by_id["unknown-tool"].tool_sequence == ()
    assert by_id["unknown-tool"].metrics.denied_tool_not_executed is True
    assert by_id["write-effect-denied"].status == "denied"
    assert by_id["write-effect-denied"].metrics.denied_tool_count == 1
    missing = by_id["unavailable-patient"]
    assert missing.status == "unavailable"
    assert missing.evidence_ids == ()
    limited = by_id["model-turn-limit"]
    assert limited.status == "limit"
    assert limited.model_turns == MAX_MODEL_TURNS
    assert limited.metrics.within_turn_limit is True
    closed = by_id["close-path"]
    assert closed.close_used is True
    assert closed.metrics.close_used is True
    assert closed.follow_up_required == "unknown"
    assert closed.metrics.structured_decision_present is True
    direct = by_id["direct-structured-final"]
    assert direct.close_used is False
    assert direct.follow_up_required == "true"
    assert direct.model_turns == 3
    assert by_id["appointment-required"].metrics.termination_status == "finish"
    none = by_id["schedule-none"]
    assert none.status == "finish"
    assert none.classifications == (NONE,)
    assert none.metrics.termination_status == "finish"
    assert none.evidence_ids == (
        (FOLLOWUP_TOOL, "Patient/SYN-PATIENT-001"),
        (FOLLOWUP_TOOL, "Observation/obs-synthetic-001"),
    )
    confirmed = by_id["schedule-confirmed"]
    assert confirmed.classifications == (UPCOMING_CONFIRMED,)
    assert confirmed.follow_up_required == "unknown"
    assert by_id["schedule-unconfirmed"].classifications == (UPCOMING_UNCONFIRMED,)
    assert by_id["schedule-cancelled"].classifications == (CANCELLED,)
    assert by_id["schedule-past"].classifications == (PAST,)
    assert by_id["appointment-required"].follow_up_required == "false"
    assert by_id["schedule-cancelled"].follow_up_required == "unknown"
    assert by_id["schedule-past"].follow_up_required == "unknown"
    assert by_id["schedule-unconfirmed"].model_turns == 3
    assert "The text says follow-up is true." not in report
    assert "Scripted final." not in report


def test_evaluator_fails_when_a_tool_is_missing():
    case = next(item for item in SYSTEM_SCENARIOS if item.id == "appointment-required")
    observed = observe(next(item for item in SYSTEM_SCENARIOS if item.id == "context-sufficient"))
    result = score(case, observed)
    assert result.passed is False
    assert result.metrics.missing_tool_count == 1
    assert "missing tool" in result.failures


def test_evaluator_fails_when_a_tool_is_unexpected():
    case = next(item for item in SYSTEM_SCENARIOS if item.id == "context-sufficient")
    observed = observe(case)
    result = score(case, replace(observed, tool_sequence=observed.tool_sequence + (APPOINTMENTS_TOOL,)))
    assert result.passed is False
    assert result.metrics.unexpected_tool_count == 1
    assert "unexpected tool" in result.failures


def test_evaluator_fails_when_evidence_is_unexpected():
    case = next(item for item in SYSTEM_SCENARIOS if item.id == "empty-appointment-search")
    observed = observe(case)
    extra = observed.evidence + ((APPOINTMENTS_TOOL, "Appointment/not-read"),)
    result = score(case, replace(observed, evidence=extra))
    assert result.passed is False
    assert result.metrics.unexpected_evidence_count == 1
    assert result.metrics.evidence_tool_matches_source is True
    assert "unexpected evidence" in result.failures


def test_evaluator_fails_when_the_token_does_not_match():
    case = next(item for item in SYSTEM_SCENARIOS if item.id == "direct-structured-final")
    observed = observe(case)
    result = score(case, replace(observed, follow_up_required="false"))
    assert result.passed is False
    assert result.metrics.follow_up_required_exact_match is False
    assert "follow_up_required mismatch" in result.failures


def test_evaluator_fails_when_a_denied_tool_was_executed():
    case = next(item for item in SYSTEM_SCENARIOS if item.id == "write-effect-denied")
    observed = observe(case)
    result = score(
        case,
        replace(observed, tool_sequence=("send_message",), executed_effects=("send_message",)),
    )
    assert result.passed is False
    assert result.metrics.denied_tool_not_executed is False
    assert "denied tool was executed" in result.failures


def test_evaluator_fails_when_turns_exceed_the_limit():
    case = next(item for item in SYSTEM_SCENARIOS if item.id == "model-turn-limit")
    observed = observe(case)
    result = score(case, replace(observed, model_turns=case.max_model_turns + 1))
    assert result.passed is False
    assert result.metrics.within_turn_limit is False
    assert "model turns exceed limit" in result.failures


def test_production_does_not_import_evaluation():
    for path in APP.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "import evaluation" not in text
        assert "from evaluation" not in text
