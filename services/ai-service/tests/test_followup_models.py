from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.followup_models import (
    CASE_IDS,
    Evidence,
    FollowUpEndpointResponse,
    FollowUpEndpointStatus,
    FollowUpRequest,
    FollowUpRequired,
    dump_followup_endpoint_response,
)


def _response(**overrides) -> FollowUpEndpointResponse:
    values = {
        "runId": "00000000-0000-0000-0000-000000000001",
        "caseId": "SYN-FOLLOWUP-001",
        "status": FollowUpEndpointStatus.COMPLETED,
        "followUpRequired": FollowUpRequired.UNKNOWN,
        "answer": "Synthetic answer.",
        "evidence": [Evidence(tool="get_patient_followup_context", id="Patient/SYN-PATIENT-001")],
    }
    values.update(overrides)
    return FollowUpEndpointResponse(**values)


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
        FollowUpRequest.model_validate({"resourceType": "Bundle", "type": "collection", "entry": []})
    with pytest.raises(ValidationError):
        FollowUpRequest.model_validate({"caseId": "SYN-FOLLOWUP-001", "patient": {"id": "SYN-PAT-001"}})


def test_external_patient_id_on_request_is_rejected():
    with pytest.raises(ValidationError):
        FollowUpRequest.model_validate({"caseId": "SYN-FOLLOWUP-001", "patientId": "external-id"})


def test_endpoint_response_serializes_the_current_contract():
    body = dump_followup_endpoint_response(_response())
    assert body == {
        "runId": "00000000-0000-0000-0000-000000000001",
        "caseId": "SYN-FOLLOWUP-001",
        "status": "completed",
        "followUpRequired": "unknown",
        "answer": "Synthetic answer.",
        "evidence": [{"tool": "get_patient_followup_context", "id": "Patient/SYN-PATIENT-001"}],
    }


@pytest.mark.parametrize(
    ("value", "serialized"),
    [
        (FollowUpRequired.TRUE, "true"),
        (FollowUpRequired.FALSE, "false"),
        (FollowUpRequired.UNKNOWN, "unknown"),
    ],
)
def test_follow_up_required_accepts_true_false_unknown(value, serialized):
    body = dump_followup_endpoint_response(_response(followUpRequired=value))
    assert body["followUpRequired"] == serialized


def test_follow_up_required_rejects_boolean_and_unknown_tokens():
    with pytest.raises(ValidationError):
        _response(followUpRequired=True)
    with pytest.raises(ValidationError):
        _response(followUpRequired="TRUE")


def test_evidence_requires_tool_and_id():
    evidence = Evidence(tool="get_patient_followup_context", id="Patient/SYN-PATIENT-001")
    assert evidence.tool == "get_patient_followup_context"
    assert evidence.id == "Patient/SYN-PATIENT-001"
    with pytest.raises(ValidationError):
        Evidence(tool="get_patient_followup_context")
    with pytest.raises(ValidationError):
        Evidence.model_validate(
            {"tool": "get_patient_followup_context", "id": "Patient/SYN-PATIENT-001", "resourceType": "Patient"}
        )


def test_endpoint_status_values():
    assert {item.value for item in FollowUpEndpointStatus} == {
        "completed",
        "denied",
        "unavailable",
        "limit",
    }
