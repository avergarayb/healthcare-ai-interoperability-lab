from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.followup_models import (
    AGENT_NAME,
    AGENT_VERSION,
    CASE_IDS,
    MAX_SUMMARY_CHARS,
    PROMPT_VERSION,
    Evidence,
    FollowUpRequest,
    FollowUpRequired,
    FollowUpResponse,
    FollowUpStatus,
    SuggestedAction,
    SuggestedActionType,
    dump_followup_response,
    followup_response,
)


def _valid_response(**overrides) -> FollowUpResponse:
    values = {
        "status": FollowUpStatus.COMPLETED,
        "run_id": "00000000-0000-0000-0000-000000000001",
        "case_id": "SYN-FOLLOWUP-001",
        "follow_up_required": FollowUpRequired.TRUE,
        "model_called": True,
        "summary": "Synthetic follow-up summary.",
        "reason": "Upcoming synthetic appointment is booked.",
        "suggested_actions": [
            SuggestedAction(type=SuggestedActionType.CONSIDER_FOLLOW_UP, detail="Review booked visit")
        ],
        "evidence": [Evidence(tool="get_upcoming_appointments", id="SYN-APT-001")],
    }
    values.update(overrides)
    return followup_response(**values)


def test_valid_request_accepts_each_known_case_id():
    for case_id in CASE_IDS:
        parsed = FollowUpRequest.model_validate({"caseId": case_id})
        assert parsed.case_id == case_id


def test_unknown_case_id_is_rejected():
    with pytest.raises(ValidationError):
        FollowUpRequest.model_validate({"caseId": "SYN-FOLLOWUP-999"})


def test_extra_request_fields_are_rejected():
    with pytest.raises(ValidationError):
        FollowUpRequest.model_validate({"caseId": "SYN-FOLLOWUP-001", "extra": "no"})


def test_bundle_and_free_clinical_context_are_rejected():
    with pytest.raises(ValidationError):
        FollowUpRequest.model_validate(
            {"resourceType": "Bundle", "type": "collection", "entry": []}
        )
    with pytest.raises(ValidationError):
        FollowUpRequest.model_validate(
            {"caseId": "SYN-FOLLOWUP-001", "patient": {"id": "SYN-PAT-001"}}
        )


def test_external_patient_id_on_request_is_rejected():
    with pytest.raises(ValidationError):
        FollowUpRequest.model_validate(
            {"caseId": "SYN-FOLLOWUP-001", "patientId": "external-id"}
        )


def test_valid_response_serializes_with_camel_case_and_string_enums():
    body = dump_followup_response(_valid_response())
    assert body == {
        "status": "COMPLETED",
        "runId": "00000000-0000-0000-0000-000000000001",
        "agent": AGENT_NAME,
        "agentVersion": AGENT_VERSION,
        "caseId": "SYN-FOLLOWUP-001",
        "followUpRequired": "true",
        "summary": "Synthetic follow-up summary.",
        "reason": "Upcoming synthetic appointment is booked.",
        "suggestedActions": [{"type": "consider-follow-up", "detail": "Review booked visit"}],
        "evidence": [{"tool": "get_upcoming_appointments", "id": "SYN-APT-001"}],
        "modelCalled": True,
        "requiresHumanReview": True,
        "promptVersion": PROMPT_VERSION,
    }


@pytest.mark.parametrize(
    ("value", "serialized"),
    [
        (FollowUpRequired.TRUE, "true"),
        (FollowUpRequired.FALSE, "false"),
        (FollowUpRequired.UNKNOWN, "unknown"),
        ("true", "true"),
        ("false", "false"),
        ("unknown", "unknown"),
    ],
)
def test_follow_up_required_accepts_true_false_unknown(value, serialized):
    body = dump_followup_response(_valid_response(follow_up_required=value))
    assert body["followUpRequired"] == serialized


def test_follow_up_required_rejects_boolean_and_unknown_tokens():
    with pytest.raises(ValidationError):
        _valid_response(follow_up_required=True)
    with pytest.raises(ValidationError):
        FollowUpResponse.model_validate(
            dump_followup_response(_valid_response()) | {"followUpRequired": "TRUE"}
        )


@pytest.mark.parametrize("action_type", ["review", "consider-follow-up", "none"])
def test_suggested_actions_accept_closed_enum(action_type):
    action = SuggestedAction(type=action_type, detail="synthetic")
    assert action.type.value == action_type


@pytest.mark.parametrize(
    "action_type",
    [
        "diagnose",
        "prescribe",
        "modify-medication",
        "modify-resource",
        "create-appointment",
        "send-message",
    ],
)
def test_suggested_actions_reject_prohibited_types(action_type):
    with pytest.raises(ValidationError):
        SuggestedAction(type=action_type, detail="no")


def test_requires_human_review_cannot_be_false():
    payload = dump_followup_response(_valid_response())
    payload["requiresHumanReview"] = False
    with pytest.raises(ValidationError):
        FollowUpResponse.model_validate(payload)


def test_factory_always_sets_requires_human_review_true():
    body = dump_followup_response(_valid_response())
    assert body["requiresHumanReview"] is True


def test_evidence_requires_tool_and_id():
    evidence = Evidence(tool="get_conditions", id="SYN-CON-001")
    assert evidence.tool == "get_conditions"
    assert evidence.id == "SYN-CON-001"
    with pytest.raises(ValidationError):
        Evidence(tool="get_conditions")
    with pytest.raises(ValidationError):
        Evidence.model_validate(
            {"tool": "get_conditions", "id": "SYN-CON-001", "resourceType": "Condition"}
        )


def test_summary_respects_076_character_limit():
    dump_followup_response(_valid_response(summary="x" * MAX_SUMMARY_CHARS))
    with pytest.raises(ValidationError):
        _valid_response(summary="x" * (MAX_SUMMARY_CHARS + 1))


def test_status_enum_includes_policy_denied():
    assert {item.value for item in FollowUpStatus} == {
        "COMPLETED",
        "DISABLED",
        "VALIDATION_ERROR",
        "POLICY_DENIED",
        "PROVIDER_ERROR",
    }
