from __future__ import annotations

import pytest

from app.followup_models import (
    MAX_SUMMARY_CHARS,
    Evidence,
    FollowUpRequired,
    FollowUpStatus,
    SuggestedAction,
    SuggestedActionType,
)
from app.followup_policy import (
    ALLOWED_TOOLS,
    MAX_TOOL_CALLS,
    TIMEOUT_SECONDS,
    PolicyDenied,
    can_make_tool_call,
    enforce_human_review,
    is_tool_allowed,
    validate_evidence,
    validate_follow_up_required,
    validate_output,
    validate_status,
    validate_suggested_actions,
    validate_summary,
    validate_tool_call,
)


def _valid_output(**overrides) -> dict:
    payload = {
        "status": "COMPLETED",
        "followUpRequired": "true",
        "summary": "Synthetic follow-up summary.",
        "suggestedActions": [{"type": "consider-follow-up", "detail": "Review booked visit"}],
        "evidence": [{"tool": "get_upcoming_appointments", "id": "SYN-APT-001"}],
        "requiresHumanReview": True,
    }
    payload.update(overrides)
    return payload


@pytest.mark.parametrize("name", ALLOWED_TOOLS)
def test_allowlist_permits_the_six_tools(name):
    assert is_tool_allowed(name) is True
    validate_tool_call(name, {"caseId": "SYN-FOLLOWUP-001"})


@pytest.mark.parametrize(
    "name",
    [
        "unknown_tool",
        "send_message",
        "create_appointment",
        "write_note",
        "delete_record",
        "update_patient",
        "modify_resource",
        "diagnose",
        "prescribe",
        "get_secret",
    ],
)
def test_non_allowlisted_tools_are_denied(name):
    assert is_tool_allowed(name) is False
    with pytest.raises(PolicyDenied, match="tool not allowed"):
        validate_tool_call(name, {"caseId": "SYN-FOLLOWUP-001"})


def test_default_deny_does_not_require_an_explicit_prohibition():
    assert is_tool_allowed("harmless_unregistered_tool") is False


def test_execution_limits_are_deterministic():
    assert MAX_TOOL_CALLS == 6
    assert TIMEOUT_SECONDS == 30
    assert can_make_tool_call(0) is True
    assert can_make_tool_call(5) is True
    assert can_make_tool_call(6) is False


def test_valid_tool_input_is_accepted():
    validate_tool_call("get_patient", {"caseId": "SYN-FOLLOWUP-006"})


def test_extra_fields_are_rejected():
    with pytest.raises(PolicyDenied):
        validate_tool_call("get_patient", {"caseId": "SYN-FOLLOWUP-001", "note": "extra"})


def test_resource_type_is_rejected():
    with pytest.raises(PolicyDenied):
        validate_tool_call(
            "get_patient",
            {"caseId": "SYN-FOLLOWUP-001", "resourceType": "Patient"},
        )


def test_bundle_is_rejected():
    with pytest.raises(PolicyDenied):
        validate_tool_call(
            "get_conditions",
            {"resourceType": "Bundle", "type": "collection", "entry": []},
        )


def test_external_patient_id_is_rejected():
    with pytest.raises(PolicyDenied):
        validate_tool_call(
            "get_patient",
            {"caseId": "SYN-FOLLOWUP-001", "patientId": "external-id"},
        )


def test_unknown_case_id_is_rejected_without_being_an_empty_result():
    with pytest.raises(PolicyDenied, match="unknown caseId"):
        validate_tool_call("get_patient", {"caseId": "SYN-FOLLOWUP-999"})


@pytest.mark.parametrize("action_type", ["review", "consider-follow-up", "none"])
def test_allowed_suggested_actions_are_accepted(action_type):
    validate_suggested_actions([{"type": action_type, "detail": "synthetic"}])
    validate_suggested_actions([SuggestedAction(type=SuggestedActionType(action_type), detail="synthetic")])


@pytest.mark.parametrize(
    "action_type",
    [
        "diagnose",
        "prescribe",
        "modify-medication",
        "modify-resource",
        "create-appointment",
        "send-message",
        "other",
    ],
)
def test_invalid_suggested_actions_are_denied(action_type):
    with pytest.raises(PolicyDenied, match="suggested action not allowed"):
        validate_suggested_actions([{"type": action_type, "detail": "no"}])


def test_requires_human_review_false_is_rejected():
    with pytest.raises(PolicyDenied, match="requiresHumanReview must remain true"):
        enforce_human_review(False)
    with pytest.raises(PolicyDenied):
        validate_output(_valid_output(requiresHumanReview=False))


def test_requires_human_review_true_is_accepted():
    assert enforce_human_review(True) is True


@pytest.mark.parametrize("value", ["true", "false", "unknown", FollowUpRequired.UNKNOWN])
def test_follow_up_required_accepts_closed_values(value):
    validate_follow_up_required(value)


def test_follow_up_required_rejects_boolean_and_unknown_tokens():
    with pytest.raises(PolicyDenied):
        validate_follow_up_required(True)
    with pytest.raises(PolicyDenied):
        validate_follow_up_required("TRUE")


@pytest.mark.parametrize("status", list(FollowUpStatus))
def test_defined_status_values_are_accepted(status):
    validate_status(status)
    validate_status(status.value)


def test_unknown_status_is_rejected():
    with pytest.raises(PolicyDenied):
        validate_status("SUCCESS")


def test_summary_over_limit_is_rejected():
    validate_summary("x" * MAX_SUMMARY_CHARS)
    with pytest.raises(PolicyDenied, match="summary exceeds limit"):
        validate_summary("x" * (MAX_SUMMARY_CHARS + 1))


def test_evidence_is_valid_when_it_matches_observed_tool_results():
    observed = [
        {
            "tool": "get_upcoming_appointments",
            "caseId": "SYN-FOLLOWUP-001",
            "data": [{"id": "SYN-APT-001", "status": "booked"}],
        }
    ]
    validate_evidence(
        [Evidence(tool="get_upcoming_appointments", id="SYN-APT-001")],
        observed,
    )
    validate_output(_valid_output(), observed_results=observed)


def test_evidence_with_unknown_tool_is_rejected():
    observed = [
        {
            "tool": "get_patient",
            "caseId": "SYN-FOLLOWUP-001",
            "data": {"id": "SYN-PAT-001"},
        }
    ]
    with pytest.raises(PolicyDenied, match="evidence tool not allowed"):
        validate_evidence([{"tool": "send_message", "id": "SYN-PAT-001"}], observed)


def test_evidence_with_unobserved_id_is_rejected():
    observed = [
        {
            "tool": "get_patient",
            "caseId": "SYN-FOLLOWUP-001",
            "data": {"id": "SYN-PAT-001"},
        }
    ]
    with pytest.raises(PolicyDenied, match="evidence id was not observed"):
        validate_evidence([{"tool": "get_patient", "id": "SYN-PAT-999"}], observed)
    with pytest.raises(PolicyDenied, match="evidence id was not observed"):
        validate_evidence(
            [{"tool": "get_upcoming_appointments", "id": "SYN-PAT-001"}],
            observed,
        )


def test_evidence_rejects_resource_type():
    observed = [
        {
            "tool": "get_patient",
            "caseId": "SYN-FOLLOWUP-001",
            "data": {"id": "SYN-PAT-001"},
        }
    ]
    with pytest.raises(PolicyDenied, match="unsupported fields"):
        validate_evidence(
            [{"tool": "get_patient", "id": "SYN-PAT-001", "resourceType": "Patient"}],
            observed,
        )


def test_llm_send_message_is_denied_and_no_tool_is_executed(monkeypatch):
    def should_not_run(*args, **kwargs):
        raise AssertionError("tool must not run after policy deny")

    monkeypatch.setattr("app.followup_tools.get_patient", should_not_run)
    monkeypatch.setattr("app.followup_tools.get_upcoming_appointments", should_not_run)
    monkeypatch.setattr("app.followup_fixtures.get_followup_fixture", should_not_run)

    assert is_tool_allowed("send_message") is False
    with pytest.raises(PolicyDenied, match="tool not allowed: send_message"):
        validate_tool_call("send_message", {"caseId": "SYN-FOLLOWUP-001"})


def test_policy_does_not_execute_allowed_tools_either(monkeypatch):
    def should_not_run(*args, **kwargs):
        raise AssertionError("policy must not execute tools")

    monkeypatch.setattr("app.followup_tools.get_patient", should_not_run)
    monkeypatch.setattr("app.followup_fixtures.get_followup_fixture", should_not_run)
    validate_tool_call("get_patient", {"caseId": "SYN-FOLLOWUP-001"})
