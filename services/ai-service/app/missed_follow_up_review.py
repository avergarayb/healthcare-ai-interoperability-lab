"""Pure MISSED_FOLLOW_UP_REVIEW_V1 evaluation.

This module owns no reads and imports no graph, model, or HTTP code.
It evaluates an immutable snapshot assembled by the application.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.post_consultation_review import CollectionState, ProtocolEvaluationStatus


MISSED_FOLLOW_UP_REVIEW_V1 = "MISSED_FOLLOW_UP_REVIEW_V1"
REASON_MISSED = "missed_follow_up_without_confirmed_replacement"
REASON_FUTURE_BOOKED = "confirmed_future_follow_up_exists"
REASON_NO_NOSHOW = "eligible_past_noshow_absent"
REASON_START_INVALID = "appointment_start_missing_or_invalid"


@dataclass(frozen=True)
class MissedFollowUpAppointment:
    reference: str
    appointment_id: str
    status: str
    start: datetime | None


@dataclass(frozen=True)
class MissedFollowUpSnapshot:
    patient_id: str | None
    patient_state: CollectionState
    appointment_state: CollectionState
    appointments: tuple[MissedFollowUpAppointment, ...] = ()
    acquisition_reason_codes: tuple[str, ...] = ()
    evaluated_at: datetime | None = None


@dataclass(frozen=True)
class MissedFollowUpEvaluation:
    status: ProtocolEvaluationStatus
    reason_codes: tuple[str, ...]
    provenance_resources: tuple[str, ...]
    triggers: tuple[str, ...] = ()


def evaluate_missed_follow_up(snapshot: MissedFollowUpSnapshot) -> MissedFollowUpEvaluation:
    """Evaluate one authorized Appointment collection. This does not interpret clinical meaning."""
    states = (snapshot.patient_state, snapshot.appointment_state)
    if CollectionState.UNAVAILABLE in states:
        reasons = snapshot.acquisition_reason_codes or ("acquisition_unavailable",)
        return _evaluation(ProtocolEvaluationStatus.UNAVAILABLE, reasons)
    if CollectionState.PARTIAL in states:
        reasons = snapshot.acquisition_reason_codes or ("bounded_search_incomplete",)
        return _evaluation(ProtocolEvaluationStatus.INSUFFICIENT, reasons)
    if CollectionState.NOT_READ in states:
        return _evaluation(ProtocolEvaluationStatus.NOT_EVALUATED, ("required_collection_not_read",))
    if not snapshot.patient_id or snapshot.evaluated_at is None:
        return _evaluation(ProtocolEvaluationStatus.UNAVAILABLE, ("authorized_patient_missing",))

    instant = snapshot.evaluated_at
    past_noshow = [
        item
        for item in snapshot.appointments
        if item.status == "noshow" and item.start is not None and item.start < instant
    ]
    future_booked = [
        item
        for item in snapshot.appointments
        if item.status == "booked" and item.start is not None and item.start >= instant
    ]
    ambiguous_booked = [
        item for item in snapshot.appointments if item.status == "booked" and item.start is None
    ]
    invalid_noshow = [
        item for item in snapshot.appointments if item.status == "noshow" and item.start is None
    ]
    if future_booked:
        provenance = _refs(_by_start(past_noshow)) + _refs(_by_start(future_booked))
        return _evaluation(
            ProtocolEvaluationStatus.NOT_MATCHED,
            (REASON_FUTURE_BOOKED,),
            provenance,
        )
    if past_noshow and ambiguous_booked:
        provenance = _refs(_by_start(past_noshow)) + _refs(_by_id(ambiguous_booked))
        return _evaluation(ProtocolEvaluationStatus.INSUFFICIENT, (REASON_START_INVALID,), provenance)
    if not past_noshow and invalid_noshow:
        return _evaluation(
            ProtocolEvaluationStatus.INSUFFICIENT,
            (REASON_START_INVALID,),
            _refs(_by_id(invalid_noshow)),
        )
    if past_noshow:
        triggers = _refs(_by_start(past_noshow))
        return _evaluation(
            ProtocolEvaluationStatus.MATCHED,
            (REASON_MISSED,),
            triggers,
            triggers,
        )
    return _evaluation(ProtocolEvaluationStatus.NOT_MATCHED, (REASON_NO_NOSHOW,))


def _evaluation(
    status: ProtocolEvaluationStatus,
    reasons: tuple[str, ...],
    provenance: tuple[str, ...] = (),
    triggers: tuple[str, ...] = (),
) -> MissedFollowUpEvaluation:
    return MissedFollowUpEvaluation(
        status=status,
        reason_codes=reasons,
        provenance_resources=provenance,
        triggers=triggers if status is ProtocolEvaluationStatus.MATCHED else (),
    )


def _by_start(items: list[MissedFollowUpAppointment]) -> tuple[MissedFollowUpAppointment, ...]:
    return tuple(sorted(items, key=lambda item: (item.start, item.appointment_id)))


def _by_id(items: list[MissedFollowUpAppointment]) -> tuple[MissedFollowUpAppointment, ...]:
    return tuple(sorted(items, key=lambda item: item.appointment_id))


def _refs(items: tuple[MissedFollowUpAppointment, ...]) -> tuple[str, ...]:
    return tuple(item.reference for item in items)
