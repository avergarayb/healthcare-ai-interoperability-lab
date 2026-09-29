"""Plain-text summary of one evaluation suite."""

from __future__ import annotations

from evaluation.runner import EvaluationResult


def format_report(results: tuple[EvaluationResult, ...] | list[EvaluationResult]) -> str:
    """Render ids, pass/fail, tool counts, turns, and the structured token."""
    rows = list(results)
    passed = sum(1 for result in rows if result.passed)
    failed = len(rows) - passed
    lines = [
        "Evaluation summary",
        "",
        f"{len(rows)} cases",
        f"{passed} passed",
        f"{failed} failed",
        "",
        f"{'CASE':<28} {'RESULT':<8} {'TOOLS':<7} {'TURNS':<7} {'FINAL'}",
    ]
    for result in rows:
        label = "PASS" if result.passed else "FAIL"
        lines.append(
            f"{result.evaluation_case_id:<28} {label:<8} {len(result.tool_sequence):<7} "
            f"{result.model_turns:<7} {result.follow_up_required}"
        )
    for result in rows:
        if result.failures:
            lines.append(f"{result.evaluation_case_id}: {', '.join(result.failures)}")
    return "\n".join(lines)
