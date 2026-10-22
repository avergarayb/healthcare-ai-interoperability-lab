from __future__ import annotations

from dataclasses import replace

import pytest

from app.post_consultation_review import (
    AppointmentFact,
    CollectionState,
    PostConsultationSnapshot,
    ProtocolEvaluationStatus,
    evaluate_post_consultation_review,
    parse_fhir_reference,
    validated_fhir_id,
)


PATIENT_ID = "patient-008"


@pytest.mark.parametrize("resource_id", ["patient.008", "a.b", "abc-123", "ABC.123-xyz"])
def test_path_safe_fhir_ids_keep_embedded_dots(resource_id: str):
    assert validated_fhir_id(resource_id) == resource_id


@pytest.mark.parametrize(
    "resource_id",
    [".", "..", "../../admin", "../x", "a/b", "a%2Fb", "", "a" * 65],
)
def test_path_unsafe_fhir_ids_are_rejected(resource_id: str):
    assert validated_fhir_id(resource_id) is None


@pytest.mark.parametrize(
    ("reference", "resource_type"),
    [
        ("Patient/.", "Patient"),
        ("Patient/..", "Patient"),
        ("Encounter/.", "Encounter"),
        ("Encounter/..", "Encounter"),
    ],
)
def test_dot_segment_references_are_rejected(reference: str, resource_type: str):
    assert parse_fhir_reference(reference, resource_type) is None


def _encounter(encounter_id: str = "enc-1", end: object = "2026-09-29T10:00:00Z") -> dict:
    return {
        "resourceType": "Encounter",
        "id": encounter_id,
        "status": "finished",
        "subject": {"reference": f"Patient/{PATIENT_ID}"},
        "period": {"end": end},
    }


def _observation(
    observation_id: str = "obs-1",
    encounter_id: str = "enc-1",
    issued: object = "2026-09-29T10:00:01Z",
) -> dict:
    return {
        "resourceType": "Observation",
        "id": observation_id,
        "status": "final",
        "subject": {"reference": f"Patient/{PATIENT_ID}"},
        "encounter": {"reference": f"Encounter/{encounter_id}"},
        "issued": issued,
        "effectiveDateTime": "1900-01-01T00:00:00Z",
        "valueString": "must not influence the protocol",
    }


def _snapshot(**overrides) -> PostConsultationSnapshot:
    values = {
        "patient_id": PATIENT_ID,
        "patient_state": CollectionState.COMPLETE,
        "encounter_state": CollectionState.COMPLETE,
        "observation_state": CollectionState.COMPLETE,
        "appointment_state": CollectionState.COMPLETE,
        "encounters": (_encounter(),),
        "observations": (_observation(),),
        "appointments": (),
    }
    values.update(overrides)
    return PostConsultationSnapshot(**values)


def test_valid_explicit_pair_with_complete_empty_schedule_matches():
    result = evaluate_post_consultation_review(_snapshot())
    assert result.evaluation_status is ProtocolEvaluationStatus.MATCHED
    assert result.matched_resources == ("Encounter/enc-1", "Observation/obs-1")
    assert result.human_review_status == "required"
    assert result.action_status == "proposed"
    assert result.action_type == "review_follow_up_case"


def test_upcoming_confirmed_blocks_an_otherwise_matching_pair():
    result = evaluate_post_consultation_review(
        _snapshot(
            appointments=(
                AppointmentFact("Appointment/cancelled", "CANCELLED"),
                AppointmentFact("Appointment/booked", "UPCOMING_CONFIRMED"),
                AppointmentFact("Appointment/pending", "UPCOMING_UNCONFIRMED"),
                AppointmentFact("Appointment/ambiguous", "OTHER"),
            )
        )
    )
    assert result.evaluation_status is ProtocolEvaluationStatus.NOT_MATCHED
    assert result.reason_codes == ("upcoming_confirmed_appointment",)
    assert result.matched_resources[-1] == "Appointment/booked"
    assert result.human_review_status == "not_proposed"
    assert result.action_status == "not_proposed"


@pytest.mark.parametrize("classification", ["UPCOMING_UNCONFIRMED", "CANCELLED", "PAST"])
def test_nonblocking_appointment_classifications_still_match(classification: str):
    result = evaluate_post_consultation_review(
        _snapshot(appointments=(AppointmentFact("Appointment/a", classification),))
    )
    assert result.evaluation_status is ProtocolEvaluationStatus.MATCHED


def test_other_without_confirmed_is_insufficient():
    result = evaluate_post_consultation_review(
        _snapshot(appointments=(AppointmentFact("Appointment/a", "OTHER"),))
    )
    assert result.evaluation_status is ProtocolEvaluationStatus.INSUFFICIENT


def test_complete_search_with_no_final_observation_is_insufficient():
    result = evaluate_post_consultation_review(_snapshot(observations=()))
    assert result.evaluation_status is ProtocolEvaluationStatus.INSUFFICIENT
    assert result.reason_codes == ("final_observation_missing",)


def test_observation_for_an_unfetched_encounter_does_not_fabricate_a_pair():
    result = evaluate_post_consultation_review(
        _snapshot(observations=(_observation(encounter_id="foreign"),))
    )
    assert result.evaluation_status is ProtocolEvaluationStatus.INSUFFICIENT
    assert result.reason_codes == ("explicit_encounter_association_missing",)


@pytest.mark.parametrize(
    ("encounter_end", "issued", "reason"),
    [
        (None, "2026-09-29T10:00:01Z", "encounter_end_missing_or_invalid"),
        ("2026-09-29T10:00:00Z", None, "observation_issued_missing_or_invalid"),
        ("2026-09-29T10:00:00Z", "2026-09-29T10:00:01", "observation_issued_missing_or_invalid"),
        ("2026-09-29T10:00:00Z", "2026-09", "observation_issued_missing_or_invalid"),
        ("2026-09-29T10:00:00Z", "not-a-date", "observation_issued_missing_or_invalid"),
    ],
)
def test_missing_partial_naive_or_invalid_timestamps_are_insufficient(
    encounter_end: object,
    issued: object,
    reason: str,
):
    result = evaluate_post_consultation_review(
        _snapshot(encounters=(_encounter(end=encounter_end),), observations=(_observation(issued=issued),))
    )
    assert result.evaluation_status is ProtocolEvaluationStatus.INSUFFICIENT
    assert reason in result.reason_codes


def test_equal_timestamps_match_after_utc_normalization():
    result = evaluate_post_consultation_review(
        _snapshot(
            encounters=(_encounter(end="2026-09-29T05:00:00-05:00"),),
            observations=(_observation(issued="2026-09-29T10:00:00Z"),),
        )
    )
    assert result.evaluation_status is ProtocolEvaluationStatus.MATCHED


@pytest.mark.parametrize(
    "fraction",
    ["", ".1", ".123", ".123456"],
)
def test_supported_fractional_precision_remains_comparable(fraction: str):
    timestamp = f"2026-09-29T10:00:00{fraction}Z"
    result = evaluate_post_consultation_review(
        _snapshot(encounters=(_encounter(end=timestamp),), observations=(_observation(issued=timestamp),))
    )
    assert result.evaluation_status is ProtocolEvaluationStatus.MATCHED


@pytest.mark.parametrize("fraction", [".0000001", ".123456789"])
def test_precision_beyond_six_fractional_digits_is_insufficient(fraction: str):
    result = evaluate_post_consultation_review(
        _snapshot(
            encounters=(_encounter(end="2026-09-29T10:00:00.0000002Z"),),
            observations=(_observation(issued=f"2026-09-29T10:00:00{fraction}Z"),),
        )
    )
    assert result.evaluation_status is ProtocolEvaluationStatus.INSUFFICIENT


def test_one_microsecond_before_and_after_are_not_truncated():
    before = evaluate_post_consultation_review(
        _snapshot(
            encounters=(_encounter(end="2026-09-29T10:00:00.000002Z"),),
            observations=(_observation(issued="2026-09-29T10:00:00.000001Z"),),
        )
    )
    after = evaluate_post_consultation_review(
        _snapshot(
            encounters=(_encounter(end="2026-09-29T10:00:00.000001Z"),),
            observations=(_observation(issued="2026-09-29T10:00:00.000002Z"),),
        )
    )
    assert before.evaluation_status is ProtocolEvaluationStatus.NOT_MATCHED
    assert after.evaluation_status is ProtocolEvaluationStatus.MATCHED


@pytest.mark.parametrize(
    "reference",
    [
        "Encounter/foreign?alias=/Encounter/enc-1",
        "Encounter/enc-1?alias=x",
        "Encounter/enc-1#fragment",
        "https://evil.example/fhir/Encounter/enc-1",
        "Patient/enc-1",
        "Encounter/enc-1/extra",
        "Encounter%2Fenc-1",
    ],
)
def test_noncanonical_encounter_references_do_not_form_a_pair(reference: str):
    observation = _observation()
    observation["encounter"] = {"reference": reference}
    result = evaluate_post_consultation_review(_snapshot(observations=(observation,)))
    assert result.evaluation_status is ProtocolEvaluationStatus.INSUFFICIENT
    assert result.matched_resources == ()


def test_issued_before_end_is_not_matched_and_effective_datetime_is_ignored():
    result = evaluate_post_consultation_review(
        _snapshot(observations=(_observation(issued="2026-09-29T09:59:59Z"),))
    )
    assert result.evaluation_status is ProtocolEvaluationStatus.NOT_MATCHED
    assert result.reason_codes == ("observation_issued_before_encounter_end",)


def test_multiple_encounters_use_only_the_explicit_association():
    result = evaluate_post_consultation_review(
        _snapshot(
            encounters=(
                _encounter("enc-latest", "2026-09-30T10:00:00Z"),
                _encounter("enc-linked", "2026-09-28T10:00:00Z"),
            ),
            observations=(_observation(encounter_id="enc-linked", issued="2026-09-28T10:00:00Z"),),
        )
    )
    assert result.evaluation_status is ProtocolEvaluationStatus.MATCHED
    assert "Encounter/enc-linked" in result.matched_resources
    assert "Encounter/enc-latest" not in result.matched_resources


@pytest.mark.parametrize(
    ("field", "state", "expected"),
    [
        ("encounter_state", CollectionState.PARTIAL, ProtocolEvaluationStatus.INSUFFICIENT),
        ("observation_state", CollectionState.UNAVAILABLE, ProtocolEvaluationStatus.UNAVAILABLE),
        ("appointment_state", CollectionState.NOT_READ, ProtocolEvaluationStatus.NOT_EVALUATED),
    ],
)
def test_collection_completeness_is_not_collapsed(field, state, expected):
    result = evaluate_post_consultation_review(replace(_snapshot(), **{field: state}))
    assert result.evaluation_status is expected
