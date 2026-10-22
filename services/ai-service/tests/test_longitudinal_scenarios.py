"""Deterministic outcomes for the longitudinal synthetic scenarios.

These tests do not add clinical rules. They show the existing protocols'
matched, not_matched, or insufficient result for each scenario shape.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.followup_review import FollowUpReviewCaseService
from app.followup_review_sqlite import SQLiteFollowUpReviewCaseRepository
from app.langgraph_fhir_client import BoundedSearchResult, BoundedSearchStatus
from app.langgraph_fhir_followup import CANCELLED, UPCOMING_CONFIRMED, case_resolution_search_path
from app.longitudinal_context import build_longitudinal_context, render_timeline_html
from app.missed_follow_up_review import (
    MissedFollowUpAppointment,
    MissedFollowUpSnapshot,
    evaluate_missed_follow_up,
)
from app.post_consultation_review import (
    AppointmentFact,
    CollectionState,
    PostConsultationSnapshot,
    ProtocolEvaluationStatus,
    ProtocolReviewResult,
    POST_CONSULTATION_RESULT_REVIEW_V1,
    evaluate_post_consultation_review,
)


NOW = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)
PATIENT = "MHS-PAT-015"


def _encounter(encounter_id: str, *, end: str | None, patient: str = PATIENT) -> dict:
    period = {"start": "2026-02-01T10:00:00Z"}
    if end is not None:
        period["end"] = end
    return {
        "resourceType": "Encounter",
        "id": encounter_id,
        "status": "finished",
        "subject": {"reference": f"Patient/{patient}"},
        "period": period,
    }


def _observation(
    observation_id: str,
    encounter_id: str,
    issued: str | None,
    *,
    status: str = "final",
    patient: str = PATIENT,
) -> dict:
    resource = {
        "resourceType": "Observation",
        "id": observation_id,
        "status": status,
        "subject": {"reference": f"Patient/{patient}"},
        "encounter": {"reference": f"Encounter/{encounter_id}"},
    }
    if issued is not None:
        resource["issued"] = issued
    return resource


def _post(patient: str, encounters=(), observations=(), appointments=()) -> PostConsultationSnapshot:
    return PostConsultationSnapshot(
        patient_id=patient,
        patient_state=CollectionState.COMPLETE,
        encounter_state=CollectionState.COMPLETE,
        observation_state=CollectionState.COMPLETE,
        appointment_state=CollectionState.COMPLETE,
        encounters=tuple(encounters),
        observations=tuple(observations),
        appointments=tuple(appointments),
    )


def _missed(patient: str, appointments=(), state=CollectionState.COMPLETE) -> MissedFollowUpSnapshot:
    return MissedFollowUpSnapshot(
        patient_id=patient,
        patient_state=state,
        appointment_state=state,
        appointments=tuple(appointments),
        evaluated_at=NOW,
    )


def _visit(reference: str, status: str, start: datetime | None) -> MissedFollowUpAppointment:
    return MissedFollowUpAppointment(reference, reference.split("/", 1)[1], status, start)


def test_s01_post_consultation_result_matches_without_appointments():
    result = evaluate_post_consultation_review(
        _post(
            "MHS-PAT-006",
            [_encounter("MHS-CON-015", end="2026-06-01T10:00:00Z", patient="MHS-PAT-006")],
            [_observation("MHS-RES-015", "MHS-CON-015", "2026-06-01T10:20:00Z", patient="MHS-PAT-006")],
        )
    )
    assert result.evaluation_status is ProtocolEvaluationStatus.MATCHED
    assert result.matched_resources == ("Encounter/MHS-CON-015", "Observation/MHS-RES-015")


def test_s02_past_noshow_without_replacement_matches():
    result = evaluate_missed_follow_up(
        _missed("MHS-PAT-004", [_visit("Appointment/MHS-APT-001", "noshow", NOW - timedelta(days=400))])
    )
    assert result.status is ProtocolEvaluationStatus.MATCHED
    assert result.reason_codes == ("missed_follow_up_without_confirmed_replacement",)


def test_s03_confirmed_replacement_does_not_match():
    result = evaluate_missed_follow_up(
        _missed(
            "MHS-PAT-007",
            [
                _visit("Appointment/MHS-APT-010", "noshow", NOW - timedelta(days=400)),
                _visit("Appointment/MHS-APT-011", "booked", NOW + timedelta(days=400)),
            ],
        )
    )
    assert result.status is ProtocolEvaluationStatus.NOT_MATCHED
    assert result.reason_codes == ("confirmed_future_follow_up_exists",)


def test_s04_cancelled_appointment_is_not_a_missed_trigger():
    missed = evaluate_missed_follow_up(
        _missed("MHS-PAT-008", [_visit("Appointment/MHS-APT-012", "cancelled", NOW - timedelta(days=30))])
    )
    assert missed.status is ProtocolEvaluationStatus.NOT_MATCHED
    assert missed.reason_codes == ("eligible_past_noshow_absent",)
    post = evaluate_post_consultation_review(
        _post(
            "MHS-PAT-008",
            [_encounter("MHS-CON-X", end="2026-02-01T10:00:00Z", patient="MHS-PAT-008")],
            [_observation("MHS-RES-X", "MHS-CON-X", "2026-02-01T11:00:00Z", patient="MHS-PAT-008")],
            [AppointmentFact("Appointment/MHS-APT-012", CANCELLED)],
        )
    )
    assert post.evaluation_status is ProtocolEvaluationStatus.MATCHED


def test_s05_noshow_without_start_is_insufficient():
    result = evaluate_missed_follow_up(
        _missed("MHS-PAT-009", [_visit("Appointment/MHS-APT-013", "noshow", None)])
    )
    assert result.status is ProtocolEvaluationStatus.INSUFFICIENT
    assert result.reason_codes == ("appointment_start_missing_or_invalid",)


def test_s06_final_result_without_issued_is_insufficient():
    result = evaluate_post_consultation_review(
        _post(
            "MHS-PAT-010",
            [_encounter("MHS-CON-019", end="2026-03-01T10:00:00Z", patient="MHS-PAT-010")],
            [_observation("MHS-RES-019", "MHS-CON-019", None, patient="MHS-PAT-010")],
        )
    )
    assert result.evaluation_status is ProtocolEvaluationStatus.INSUFFICIENT
    assert "observation_issued_missing_or_invalid" in result.reason_codes


def test_s07_finished_encounter_without_end_is_insufficient():
    result = evaluate_post_consultation_review(
        _post(
            "MHS-PAT-011",
            [_encounter("MHS-CON-020", end=None, patient="MHS-PAT-011")],
            [_observation("MHS-RES-020", "MHS-CON-020", "2026-04-01T11:00:00Z", patient="MHS-PAT-011")],
        )
    )
    assert result.evaluation_status is ProtocolEvaluationStatus.INSUFFICIENT
    assert "encounter_end_missing_or_invalid" in result.reason_codes


def test_s08_patient_without_results_is_insufficient():
    result = evaluate_post_consultation_review(
        _post("MHS-PAT-012", [_encounter("MHS-CON-021", end="2026-05-01T10:00:00Z", patient="MHS-PAT-012")])
    )
    assert result.evaluation_status is ProtocolEvaluationStatus.INSUFFICIENT
    assert result.reason_codes == ("final_observation_missing",)


def test_s09_earliest_qualifying_result_is_the_match_and_both_remain_evidence_candidates():
    first = _observation("MHS-RES-022", "MHS-CON-022", "2026-02-01T11:00:00Z", patient="MHS-PAT-013")
    second = _observation("MHS-RES-023", "MHS-CON-022", "2026-02-01T12:00:00Z", patient="MHS-PAT-013")
    result = evaluate_post_consultation_review(
        _post(
            "MHS-PAT-013",
            [_encounter("MHS-CON-022", end="2026-02-01T10:00:00Z", patient="MHS-PAT-013")],
            [first, second],
        )
    )
    assert result.evaluation_status is ProtocolEvaluationStatus.MATCHED
    assert result.matched_resources == ("Encounter/MHS-CON-022", "Observation/MHS-RES-022")


def test_s10_corrected_result_does_not_satisfy_the_final_rule():
    result = evaluate_post_consultation_review(
        _post(
            "MHS-PAT-014",
            [_encounter("MHS-CON-023", end="2026-01-15T10:00:00Z", patient="MHS-PAT-014")],
            [
                _observation(
                    "MHS-RES-025",
                    "MHS-CON-023",
                    "2026-01-15T12:00:00Z",
                    status="corrected",
                    patient="MHS-PAT-014",
                )
            ],
        )
    )
    assert result.evaluation_status is ProtocolEvaluationStatus.INSUFFICIENT
    assert result.reason_codes == ("final_observation_missing",)


def test_s11_unavailable_read_stays_unavailable():
    post = evaluate_post_consultation_review(
        PostConsultationSnapshot(
            patient_id=PATIENT,
            patient_state=CollectionState.UNAVAILABLE,
            encounter_state=CollectionState.UNAVAILABLE,
            observation_state=CollectionState.UNAVAILABLE,
            appointment_state=CollectionState.UNAVAILABLE,
            acquisition_reason_codes=("acquisition_unavailable",),
        )
    )
    missed = evaluate_missed_follow_up(_missed(PATIENT, state=CollectionState.UNAVAILABLE))
    assert post.evaluation_status is ProtocolEvaluationStatus.UNAVAILABLE
    assert missed.status is ProtocolEvaluationStatus.UNAVAILABLE


def test_s12_repeated_request_reuses_the_same_review_case(tmp_path):
    class Clock:
        def __init__(self) -> None:
            self.value = NOW

        def __call__(self):
            current = self.value
            self.value += timedelta(seconds=1)
            return current

    repository = SQLiteFollowUpReviewCaseRepository(tmp_path / "review.sqlite3", clock=Clock())
    repository.initialize()
    service = FollowUpReviewCaseService(repository)
    protocol = ProtocolReviewResult(
        id=POST_CONSULTATION_RESULT_REVIEW_V1,
        evaluation_status=ProtocolEvaluationStatus.MATCHED,
        reason_codes=("post_consultation_result_requires_review",),
        matched_resources=("Encounter/MHS-CON-022", "Observation/MHS-RES-022"),
        human_review_status="required",
        human_review_reason="deterministic_post_consultation_protocol_match",
        action_status="proposed",
        action_type="review_follow_up_case",
    )
    first = service.ensure_for_protocol("SYN-FOLLOWUP-022", protocol)
    second = service.ensure_for_protocol("SYN-FOLLOWUP-022", protocol)
    assert first is not None and second is not None
    assert first.id == second.id
    assert second.version == 1
    stored = repository.get(first.id)
    assert stored is not None
    assert stored.case_id == "SYN-FOLLOWUP-022"
    assert stored.version == 1
    assert stored.status.value == "open"


def test_s13_longitudinal_patient_is_blocked_by_the_confirmed_future_visit():
    post = evaluate_post_consultation_review(
        _post(
            PATIENT,
            [_encounter("MHS-CON-024", end="2024-06-01T10:00:00Z")],
            [_observation("MHS-RES-026", "MHS-CON-024", "2024-06-01T12:00:00Z")],
            [AppointmentFact("Appointment/MHS-APT-021", UPCOMING_CONFIRMED)],
        )
    )
    missed = evaluate_missed_follow_up(
        _missed(
            PATIENT,
            [
                _visit("Appointment/MHS-APT-020", "noshow", NOW - timedelta(days=400)),
                _visit("Appointment/MHS-APT-021", "booked", NOW + timedelta(days=400)),
            ],
        )
    )
    assert post.evaluation_status is ProtocolEvaluationStatus.NOT_MATCHED
    assert post.reason_codes == ("upcoming_confirmed_appointment",)
    assert missed.status is ProtocolEvaluationStatus.NOT_MATCHED
    assert missed.reason_codes == ("confirmed_future_follow_up_exists",)


class _Reader:
    def __init__(self, pages: dict[tuple[str, str], BoundedSearchResult]) -> None:
        self.pages = pages

    def search(self, path: str, expected_resource_type: str) -> BoundedSearchResult:
        return self.pages[(path, expected_resource_type)]


def test_longitudinal_context_keeps_gaps_relations_and_limits():
    patient = BoundedSearchResult(
        BoundedSearchStatus.COMPLETE,
        ({"resourceType": "Patient", "id": PATIENT},),
    )
    encounter = {
        "resourceType": "Encounter",
        "id": "MHS-CON-020",
        "status": "finished",
        "period": {"start": "2026-04-01T10:00:00Z"},
        "meta": {"source": "https://lab.local/mini-his"},
    }
    observation = {
        "resourceType": "Observation",
        "id": "MHS-RES-019",
        "status": "final",
        "encounter": {"reference": "Encounter/MHS-CON-019"},
        "valueQuantity": {"value": 11.0, "unit": "g/dL"},
        "meta": {"source": "https://lab.local/mini-his"},
    }
    appointment = {
        "resourceType": "Appointment",
        "id": "MHS-APT-011",
        "status": "booked",
        "start": "2099-01-01T12:00:00Z",
        "extension": [
            {
                "url": "https://lab.local/mini-his/StructureDefinition/replaces-appointment",
                "valueReference": {"reference": "Appointment/MHS-APT-010"},
            }
        ],
        "meta": {"source": "https://lab.local/mini-his"},
    }
    pages = {
        (case_resolution_search_path("SYN-FOLLOWUP-024"), "Patient"): patient,
    }
    for status in ("finished", "in-progress", "planned", "cancelled"):
        resources = (encounter,) if status == "finished" else ()
        pages[(f"Encounter?patient={PATIENT}&status={status}", "Encounter")] = BoundedSearchResult(
            BoundedSearchStatus.COMPLETE, resources
        )
    for status in ("final", "preliminary", "corrected"):
        resources = (observation,) if status == "final" else ()
        pages[(f"Observation?subject=Patient/{PATIENT}&status={status}", "Observation")] = BoundedSearchResult(
            BoundedSearchStatus.COMPLETE, resources
        )
    pages[(f"Appointment?patient={PATIENT}", "Appointment")] = BoundedSearchResult(
        BoundedSearchStatus.COMPLETE, (appointment,)
    )
    context = build_longitudinal_context(_Reader(pages), "SYN-FOLLOWUP-024")
    assert context.status == "complete"
    assert context.patient_id == PATIENT
    assert context.encounters[0].reference == "Encounter/MHS-CON-020"
    assert any(gap.code == "encounter_end_missing" for gap in context.gaps)
    assert any(gap.code == "observation_issued_missing" for gap in context.gaps)
    assert context.observations[0].recorded_value == "11.0 g/dL"
    assert context.observations[0].related == ["Encounter/MHS-CON-019"]
    assert "Appointment/MHS-APT-010" in context.appointments[0].related
    page = render_timeline_html(context)
    assert "Historial longitudinal" in page
    assert "innecesario" not in page.lower()
    assert "sqlite" not in page.lower()


def test_longitudinal_context_reports_an_unavailable_read():
    context = build_longitudinal_context(
        _Reader(
            {
                (case_resolution_search_path("SYN-FOLLOWUP-019"), "Patient"): BoundedSearchResult(
                    BoundedSearchStatus.FAILED, (), "down"
                )
            }
        ),
        "SYN-FOLLOWUP-019",
    )
    assert context.status == "unavailable"
    assert context.patient_id is None
    assert context.gaps[0].code == "acquisition_unavailable"
