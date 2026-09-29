"""Pure POST_CONSULTATION_RESULT_REVIEW_V1 evaluation.

This module owns no reads and imports no graph, model, or HTTP code.  It only
evaluates an immutable, already-authorized snapshot assembled by the
application.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Mapping


POST_CONSULTATION_RESULT_REVIEW_V1 = "POST_CONSULTATION_RESULT_REVIEW_V1"


class CollectionState(str, Enum):
    NOT_READ = "not_read"
    COMPLETE = "complete"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


class ProtocolEvaluationStatus(str, Enum):
    NOT_EVALUATED = "not_evaluated"
    MATCHED = "matched"
    NOT_MATCHED = "not_matched"
    INSUFFICIENT = "insufficient"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class AppointmentFact:
    reference: str
    classification: str


@dataclass(frozen=True)
class PostConsultationSnapshot:
    patient_id: str | None
    patient_state: CollectionState
    encounter_state: CollectionState
    observation_state: CollectionState
    appointment_state: CollectionState
    encounters: tuple[Mapping[str, object], ...] = ()
    observations: tuple[Mapping[str, object], ...] = ()
    appointments: tuple[AppointmentFact, ...] = ()
    acquisition_reason_codes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProtocolReviewResult:
    id: str
    evaluation_status: ProtocolEvaluationStatus
    reason_codes: tuple[str, ...]
    matched_resources: tuple[str, ...]
    human_review_status: str
    human_review_reason: str | None
    action_status: str
    action_type: str | None


_COMPLETE_TIMESTAMP = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$"
)
_FHIR_ID = re.compile(r"^[A-Za-z0-9.-]{1,64}$")


def evaluate_post_consultation_review(snapshot: PostConsultationSnapshot) -> ProtocolReviewResult:
    """Evaluate the protocol without interpreting any clinical value."""
    states = (
        snapshot.patient_state,
        snapshot.encounter_state,
        snapshot.observation_state,
        snapshot.appointment_state,
    )
    if CollectionState.UNAVAILABLE in states:
        reasons = snapshot.acquisition_reason_codes or ("acquisition_unavailable",)
        return _result(ProtocolEvaluationStatus.UNAVAILABLE, reasons)
    if CollectionState.PARTIAL in states:
        reasons = snapshot.acquisition_reason_codes or ("bounded_search_incomplete",)
        return _result(ProtocolEvaluationStatus.INSUFFICIENT, reasons)
    if CollectionState.NOT_READ in states:
        return _result(ProtocolEvaluationStatus.NOT_EVALUATED, ("required_collection_not_read",))
    if not snapshot.patient_id:
        return _result(ProtocolEvaluationStatus.UNAVAILABLE, ("authorized_patient_missing",))

    pair_evaluation = _evaluate_pairs(snapshot)
    if pair_evaluation.status != "qualifying":
        return _result(
            pair_evaluation.protocol_status,
            pair_evaluation.reason_codes,
            pair_evaluation.resources,
        )

    confirmed = tuple(
        fact.reference
        for fact in snapshot.appointments
        if fact.classification == "UPCOMING_CONFIRMED"
    )
    if confirmed:
        return _result(
            ProtocolEvaluationStatus.NOT_MATCHED,
            ("upcoming_confirmed_appointment",),
            pair_evaluation.resources + confirmed,
        )
    if any(fact.classification == "OTHER" for fact in snapshot.appointments):
        return _result(
            ProtocolEvaluationStatus.INSUFFICIENT,
            ("appointment_classification_ambiguous",),
        )
    return _result(
        ProtocolEvaluationStatus.MATCHED,
        ("post_consultation_result_requires_review",),
        pair_evaluation.resources,
    )


@dataclass(frozen=True)
class _PairEvaluation:
    status: str
    protocol_status: ProtocolEvaluationStatus
    reason_codes: tuple[str, ...]
    resources: tuple[str, ...] = ()


def _evaluate_pairs(snapshot: PostConsultationSnapshot) -> _PairEvaluation:
    patient_id = snapshot.patient_id or ""
    encounters: dict[str, Mapping[str, object]] = {}
    for encounter in snapshot.encounters:
        encounter_id = _valid_resource_id(encounter, "Encounter")
        if (
            encounter_id is not None
            and encounter.get("status") == "finished"
            and _belongs_to_patient(encounter.get("subject"), patient_id)
        ):
            encounters[encounter_id] = encounter
    if not encounters:
        return _insufficient("finished_encounter_missing")

    final_observations = [
        observation
        for observation in snapshot.observations
        if _valid_resource_id(observation, "Observation") is not None
        and observation.get("status") == "final"
        and _belongs_to_patient(observation.get("subject"), patient_id)
    ]
    if not final_observations:
        return _insufficient("final_observation_missing")

    saw_explicit_pair = False
    saw_ambiguous_pair = False
    negative_resources: list[str] = []
    ambiguity_reasons: set[str] = set()
    for observation in final_observations:
        encounter_id = _referenced_encounter_id(observation.get("encounter"))
        encounter = encounters.get(encounter_id or "")
        if encounter is None:
            continue
        saw_explicit_pair = True
        encounter_end = _nested_value(encounter, "period", "end")
        issued = observation.get("issued")
        end_timestamp = _parse_timestamp(encounter_end)
        issued_timestamp = _parse_timestamp(issued)
        if end_timestamp is None or issued_timestamp is None:
            saw_ambiguous_pair = True
            if end_timestamp is None:
                ambiguity_reasons.add("encounter_end_missing_or_invalid")
            if issued_timestamp is None:
                ambiguity_reasons.add("observation_issued_missing_or_invalid")
            continue
        encounter_ref = f"Encounter/{encounter['id']}"
        observation_ref = f"Observation/{observation['id']}"
        if issued_timestamp >= end_timestamp:
            return _PairEvaluation(
                status="qualifying",
                protocol_status=ProtocolEvaluationStatus.MATCHED,
                reason_codes=(),
                resources=(encounter_ref, observation_ref),
            )
        negative_resources.extend((encounter_ref, observation_ref))

    if not saw_explicit_pair:
        return _insufficient("explicit_encounter_association_missing")
    if saw_ambiguous_pair:
        return _PairEvaluation(
            status="insufficient",
            protocol_status=ProtocolEvaluationStatus.INSUFFICIENT,
            reason_codes=tuple(sorted(ambiguity_reasons)),
        )
    return _PairEvaluation(
        status="not_matched",
        protocol_status=ProtocolEvaluationStatus.NOT_MATCHED,
        reason_codes=("observation_issued_before_encounter_end",),
        resources=_deduplicated(negative_resources),
    )


def _insufficient(reason: str) -> _PairEvaluation:
    return _PairEvaluation(
        status="insufficient",
        protocol_status=ProtocolEvaluationStatus.INSUFFICIENT,
        reason_codes=(reason,),
    )


def _result(
    status: ProtocolEvaluationStatus,
    reasons: tuple[str, ...],
    resources: tuple[str, ...] = (),
) -> ProtocolReviewResult:
    if status is ProtocolEvaluationStatus.MATCHED:
        return ProtocolReviewResult(
            id=POST_CONSULTATION_RESULT_REVIEW_V1,
            evaluation_status=status,
            reason_codes=reasons,
            matched_resources=resources,
            human_review_status="required",
            human_review_reason="deterministic_post_consultation_protocol_match",
            action_status="proposed",
            action_type="review_follow_up_case",
        )
    if status is ProtocolEvaluationStatus.NOT_MATCHED:
        return ProtocolReviewResult(
            id=POST_CONSULTATION_RESULT_REVIEW_V1,
            evaluation_status=status,
            reason_codes=reasons,
            matched_resources=resources,
            human_review_status="not_proposed",
            human_review_reason=None,
            action_status="not_proposed",
            action_type=None,
        )
    return ProtocolReviewResult(
        id=POST_CONSULTATION_RESULT_REVIEW_V1,
        evaluation_status=status,
        reason_codes=reasons,
        matched_resources=resources,
        human_review_status=(
            "not_determined"
            if status is not ProtocolEvaluationStatus.NOT_EVALUATED
            else "not_evaluated"
        ),
        human_review_reason=None,
        action_status="not_determined",
        action_type=None,
    )


def _valid_resource_id(resource: Mapping[str, object], resource_type: str) -> str | None:
    resource_id = resource.get("id")
    if resource.get("resourceType") != resource_type:
        return None
    return validated_fhir_id(resource_id)


def validated_fhir_id(value: object) -> str | None:
    """Return one path-safe FHIR R4 id without normalizing it."""
    if not isinstance(value, str) or value in {".", ".."}:
        return None
    return value if _FHIR_ID.fullmatch(value) is not None else None


def parse_fhir_reference(reference: object, resource_type: str) -> str | None:
    """Parse the strict relative references accepted by this V1 protocol."""
    if not isinstance(reference, str):
        return None
    prefix = f"{resource_type}/"
    if not reference.startswith(prefix):
        return None
    resource_id = reference[len(prefix) :]
    if "/" in resource_id or "?" in resource_id or "#" in resource_id:
        return None
    return validated_fhir_id(resource_id)


def _belongs_to_patient(subject: object, patient_id: str) -> bool:
    reference = subject.get("reference") if isinstance(subject, Mapping) else None
    return parse_fhir_reference(reference, "Patient") == patient_id


def _referenced_encounter_id(encounter: object) -> str | None:
    reference = encounter.get("reference") if isinstance(encounter, Mapping) else None
    return parse_fhir_reference(reference, "Encounter")


def _nested_value(resource: Mapping[str, object], parent: str, child: str) -> object:
    value = resource.get(parent)
    return value.get(child) if isinstance(value, Mapping) else None


def _parse_timestamp(raw: object) -> datetime | None:
    if not isinstance(raw, str) or _COMPLETE_TIMESTAMP.fullmatch(raw) is None:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _deduplicated(resources: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(resources))


def not_evaluated_protocol() -> ProtocolReviewResult:
    return _result(ProtocolEvaluationStatus.NOT_EVALUATED, ("required_collection_not_read",))
