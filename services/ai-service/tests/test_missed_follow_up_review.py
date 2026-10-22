"""Pure MISSED_FOLLOW_UP_REVIEW_V1 decisions."""

from __future__ import annotations

from datetime import datetime, timezone

from app.missed_follow_up_review import (
    REASON_FUTURE_BOOKED,
    REASON_MISSED,
    REASON_NO_NOSHOW,
    REASON_START_INVALID,
    MissedFollowUpAppointment,
    MissedFollowUpSnapshot,
    evaluate_missed_follow_up,
)
from app.post_consultation_review import CollectionState, ProtocolEvaluationStatus


NOW = datetime(2026, 9, 29, tzinfo=timezone.utc)


def _appointment(appointment_id: str, status: str, start: datetime | None) -> MissedFollowUpAppointment:
    return MissedFollowUpAppointment(
        reference=f"Appointment/{appointment_id}",
        appointment_id=appointment_id,
        status=status,
        start=start,
    )


def _snapshot(*appointments: MissedFollowUpAppointment, **overrides) -> MissedFollowUpSnapshot:
    values = {
        "patient_id": "patient-008",
        "patient_state": CollectionState.COMPLETE,
        "appointment_state": CollectionState.COMPLETE,
        "appointments": appointments,
        "evaluated_at": NOW,
    }
    values.update(overrides)
    return MissedFollowUpSnapshot(**values)


def test_past_noshow_without_future_booked_matches_one_trigger():
    result = evaluate_missed_follow_up(
        _snapshot(_appointment("noshow-1", "noshow", datetime(2026, 1, 1, tzinfo=timezone.utc)))
    )
    assert result.status is ProtocolEvaluationStatus.MATCHED
    assert result.reason_codes == (REASON_MISSED,)
    assert result.triggers == ("Appointment/noshow-1",)


def test_future_booked_blocks_match():
    result = evaluate_missed_follow_up(
        _snapshot(
            _appointment("noshow-1", "noshow", datetime(2026, 1, 1, tzinfo=timezone.utc)),
            _appointment("booked-1", "booked", datetime(2027, 1, 1, tzinfo=timezone.utc)),
        )
    )
    assert result.status is ProtocolEvaluationStatus.NOT_MATCHED
    assert result.reason_codes == (REASON_FUTURE_BOOKED,)
    assert result.triggers == ()
    assert result.provenance_resources == ("Appointment/noshow-1", "Appointment/booked-1")


def test_cancelled_and_proposed_are_not_triggers():
    cancelled = evaluate_missed_follow_up(
        _snapshot(_appointment("cancelled-1", "cancelled", datetime(2026, 1, 1, tzinfo=timezone.utc)))
    )
    proposed = evaluate_missed_follow_up(
        _snapshot(_appointment("proposed-1", "proposed", datetime(2027, 1, 1, tzinfo=timezone.utc)))
    )
    assert cancelled.status is ProtocolEvaluationStatus.NOT_MATCHED
    assert cancelled.reason_codes == (REASON_NO_NOSHOW,)
    assert proposed.reason_codes == (REASON_NO_NOSHOW,)


def test_noshow_without_a_start_is_insufficient():
    result = evaluate_missed_follow_up(_snapshot(_appointment("noshow-1", "noshow", None)))
    assert result.status is ProtocolEvaluationStatus.INSUFFICIENT
    assert result.reason_codes == (REASON_START_INVALID,)
    assert result.triggers == ()


def test_booked_equal_to_the_evaluation_instant_blocks_match():
    result = evaluate_missed_follow_up(
        _snapshot(
            _appointment("noshow-1", "noshow", datetime(2026, 1, 1, tzinfo=timezone.utc)),
            _appointment("booked-now", "booked", NOW),
        )
    )
    assert result.status is ProtocolEvaluationStatus.NOT_MATCHED
    assert result.reason_codes == (REASON_FUTURE_BOOKED,)


def test_ambiguous_booked_start_is_insufficient_until_a_future_booked_is_proven():
    past = _appointment("noshow-1", "noshow", datetime(2026, 1, 1, tzinfo=timezone.utc))
    ambiguous = _appointment("booked-unknown", "booked", None)
    insufficient = evaluate_missed_follow_up(_snapshot(past, ambiguous))
    assert insufficient.status is ProtocolEvaluationStatus.INSUFFICIENT
    assert insufficient.reason_codes == (REASON_START_INVALID,)
    proven = evaluate_missed_follow_up(
        _snapshot(past, ambiguous, _appointment("booked-future", "booked", datetime(2027, 3, 1, tzinfo=timezone.utc)))
    )
    assert proven.status is ProtocolEvaluationStatus.NOT_MATCHED
    assert proven.reason_codes == (REASON_FUTURE_BOOKED,)
    assert "Appointment/booked-unknown" not in proven.provenance_resources
    assert proven.provenance_resources[-1] == "Appointment/booked-future"


def test_multiple_past_noshow_triggers_are_ordered_by_start_then_id():
    same = datetime(2026, 2, 1, tzinfo=timezone.utc)
    result = evaluate_missed_follow_up(
        _snapshot(
            _appointment("b", "noshow", same),
            _appointment("a", "noshow", same),
            _appointment("earlier", "noshow", datetime(2026, 1, 1, tzinfo=timezone.utc)),
        )
    )
    assert result.triggers == ("Appointment/earlier", "Appointment/a", "Appointment/b")


def test_future_noshow_is_not_a_trigger():
    result = evaluate_missed_follow_up(
        _snapshot(_appointment("later", "noshow", datetime(2027, 1, 1, tzinfo=timezone.utc)))
    )
    assert result.status is ProtocolEvaluationStatus.NOT_MATCHED
    assert result.reason_codes == (REASON_NO_NOSHOW,)


def test_acquisition_failures_precede_appointment_rules():
    noshow = _appointment("noshow-1", "noshow", datetime(2026, 1, 1, tzinfo=timezone.utc))
    unavailable = evaluate_missed_follow_up(
        _snapshot(
            noshow,
            appointment_state=CollectionState.UNAVAILABLE,
            acquisition_reason_codes=("appointment_acquisition_unavailable",),
        )
    )
    partial = evaluate_missed_follow_up(
        _snapshot(
            noshow,
            appointment_state=CollectionState.PARTIAL,
            acquisition_reason_codes=("appointment_search_incomplete",),
        )
    )
    unread = evaluate_missed_follow_up(_snapshot(appointment_state=CollectionState.NOT_READ))
    assert unavailable.status is ProtocolEvaluationStatus.UNAVAILABLE
    assert unavailable.reason_codes == ("appointment_acquisition_unavailable",)
    assert partial.status is ProtocolEvaluationStatus.INSUFFICIENT
    assert unread.status is ProtocolEvaluationStatus.NOT_EVALUATED
