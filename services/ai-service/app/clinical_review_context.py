"""Current FHIR projection for one open follow-up review case.

FHIR remains the source of current clinical facts. The durable review case
supplies immutable trigger provenance and the persisted case id. This module
does not evaluate a protocol, call a model, or store the projection.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from app.followup_review import (
    FollowUpReviewCase,
    FollowUpReviewCaseRepository,
    ReviewCaseNotFound,
    ReviewCaseStatus,
    ReviewPersistenceUnavailable,
    canonical_reason_codes,
)
from app.langgraph_fhir_client import BoundedSearchStatus, ReadClientError
from app.langgraph_fhir_followup import (
    CANCELLED,
    NONE,
    OTHER,
    PAST,
    UPCOMING_CONFIRMED,
    UPCOMING_UNCONFIRMED,
    _appointment_view,
    _patient_id_from_case_search,
    case_resolution_search_path,
    protocol_appointment_search_path,
    schedule_classifications,
)
from app.langgraph_fhir_hapi import ExactResourceNotFound
from app.missed_follow_up_review import MISSED_FOLLOW_UP_REVIEW_V1
from app.post_consultation_review import (
    POST_CONSULTATION_RESULT_REVIEW_V1,
    parse_fhir_reference,
)


SCHEMA = "CLINICAL_REVIEW_CONTEXT_V1"
MAX_TEXT = 512
MAX_CODINGS = 10
MAX_COMPONENTS = 25
_VALUE_KEYS = (
    "valueQuantity",
    "valueCodeableConcept",
    "valueString",
    "valueBoolean",
    "valueInteger",
    "valueRange",
)
_COMPARATORS = frozenset({"<", "<=", ">=", ">"})
_ITEM_CLASSIFICATIONS = frozenset(
    {UPCOMING_CONFIRMED, UPCOMING_UNCONFIRMED, CANCELLED, PAST, OTHER}
)
AppointmentItemClassification = Literal[
    "UPCOMING_CONFIRMED",
    "UPCOMING_UNCONFIRMED",
    "CANCELLED",
    "PAST",
    "OTHER",
]
AppointmentCollectionClassification = Literal[
    "UPCOMING_CONFIRMED",
    "UPCOMING_UNCONFIRMED",
    "CANCELLED",
    "PAST",
    "OTHER",
    "NONE",
]
RetrievalReason = Literal[
    "current_context_complete",
    "provenance_encounter_not_found",
    "provenance_observation_not_found",
    "provenance_appointment_not_found",
]


class ClinicalContextClosed(Exception):
    """An open review case is required before current clinical context is read."""


class ClinicalContextUnavailable(Exception):
    """Current clinical context cannot be trusted for this request."""


class _ExactReadClient(Protocol):
    def search(self, path: str, expected_resource_type: str): ...

    def read_exact(self, resource_type: str, resource_id: str) -> dict: ...


class ReviewCaseRef(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    review_case_id: str = Field(alias="reviewCaseId")
    status: Literal["open"]
    version: int = Field(ge=1)


class TriggerProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    protocol_id: Literal[
        "POST_CONSULTATION_RESULT_REVIEW_V1",
        "MISSED_FOLLOW_UP_REVIEW_V1",
    ] = Field(alias="protocolId")
    evaluation_status: Literal["matched"] = Field(alias="evaluationStatus")
    reason_codes: list[str] = Field(alias="reasonCodes")
    matched_resources: list[str] = Field(alias="matchedResources")
    created_at: str = Field(alias="createdAt")


class RetrievalState(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    status: Literal["complete", "provenance_resource_not_found"]
    retrieved_at: str = Field(alias="retrievedAt")
    source: Literal["fhir_current"]
    reason_codes: list[RetrievalReason] = Field(alias="reasonCodes")


class PatientProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resolution: Literal["resolved"]


class EncounterPeriod(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: str | None = None
    end: str | None = None


class EncounterAvailable(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reference: str
    availability: Literal["available"]
    status: str
    period: EncounterPeriod | None = None


class EncounterMissing(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reference: str
    availability: Literal["not_found"]


class CodingEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    system: str | None = None
    code: str | None = None
    display: str | None = None


class ObservationCode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["available", "not_projected"]
    coding: list[CodingEntry] | None = None
    text: str | None = None


class QuantityFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: int | float
    comparator: str | None = None
    unit: str | None = None
    system: str | None = None
    code: str | None = None


class QuantityContent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["available"]
    kind: Literal["quantity"]
    value: int | float
    comparator: str | None = None
    unit: str | None = None
    system: str | None = None
    code: str | None = None


class CodedContent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["available"]
    kind: Literal["coded"]
    coding: list[CodingEntry]
    text: str | None = None


class StringContent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["available"]
    kind: Literal["string"]
    value: str


class BooleanContent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["available"]
    kind: Literal["boolean"]
    value: bool


class IntegerContent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["available"]
    kind: Literal["integer"]
    value: int


class RangeContent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["available"]
    kind: Literal["range"]
    low: QuantityFields | None = None
    high: QuantityFields | None = None


class ComponentContent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: ObservationCode
    value: (
        QuantityContent
        | CodedContent
        | StringContent
        | BooleanContent
        | IntegerContent
        | RangeContent
    )


class ComponentsContent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["available"]
    kind: Literal["components"]
    components: list[ComponentContent]


class NotProjectedContent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["not_projected"]


ObservationContent = (
    QuantityContent
    | CodedContent
    | StringContent
    | BooleanContent
    | IntegerContent
    | RangeContent
    | ComponentsContent
    | NotProjectedContent
)


class ObservationAvailable(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    reference: str
    availability: Literal["available"]
    status: str
    issued: str | None = None
    encounter_reference: str = Field(alias="encounterReference")
    code: ObservationCode
    content: ObservationContent


class ObservationMissing(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reference: str
    availability: Literal["not_found"]


class AppointmentItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reference: str
    status: str
    start: str | None = None
    classification: AppointmentItemClassification


class AppointmentProjection(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    collection_status: Literal["complete"] = Field(alias="collectionStatus")
    classifications: list[AppointmentCollectionClassification]
    items: list[AppointmentItem]


class TriggerAppointmentAvailable(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reference: str
    availability: Literal["available"]
    status: str
    start: str | None = None


class TriggerAppointmentMissing(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reference: str
    availability: Literal["not_found"]


class CurrentContext(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    patient: PatientProjection
    encounter: EncounterAvailable | EncounterMissing | None = None
    observation: ObservationAvailable | ObservationMissing | None = None
    trigger_appointment: TriggerAppointmentAvailable | TriggerAppointmentMissing | None = Field(
        default=None,
        alias="triggerAppointment",
    )
    appointments: AppointmentProjection


class ClinicalReviewContextResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_name: Literal["CLINICAL_REVIEW_CONTEXT_V1"] = Field(
        default="CLINICAL_REVIEW_CONTEXT_V1",
        alias="schema",
    )
    review_case: ReviewCaseRef = Field(alias="reviewCase")
    trigger_provenance: TriggerProvenance = Field(alias="triggerProvenance")
    retrieval: RetrievalState
    current_context: CurrentContext = Field(alias="currentContext")


def dump_clinical_review_context(response: ClinicalReviewContextResponse) -> dict:
    return response.model_dump(by_alias=True, mode="json", exclude_none=True)


def project_observation_code(code: object) -> ObservationCode:
    """Project a bounded code. Oversized optional text is not truncated or returned."""
    if code is None:
        return ObservationCode(status="not_projected")
    if not isinstance(code, dict):
        return ObservationCode(status="not_projected")
    text = code.get("text")
    if text is not None and not isinstance(text, str):
        return ObservationCode(status="not_projected")
    if isinstance(text, str) and len(text) > MAX_TEXT:
        return ObservationCode(status="not_projected")
    projected_text = text if isinstance(text, str) and text.strip() else None
    raw_coding = code.get("coding")
    if raw_coding is None:
        raw_coding = []
    if not isinstance(raw_coding, list) or len(raw_coding) > MAX_CODINGS:
        return ObservationCode(status="not_projected")
    entries: list[CodingEntry] = []
    for item in raw_coding:
        projected = _project_coding(item)
        if projected is None:
            return ObservationCode(status="not_projected")
        entries.append(projected)
    if not entries and projected_text is None:
        return ObservationCode(status="not_projected")
    return ObservationCode(status="available", coding=entries, text=projected_text)


def project_observation_content(resource: dict) -> ObservationContent:
    """Project one closed value or components. Unsupported content is not_projected."""
    present = [key for key in resource if isinstance(key, str) and key.startswith("value")]
    components = resource.get("component")
    has_components = components is not None
    if has_components and present:
        return NotProjectedContent(status="not_projected")
    if has_components:
        return _project_components(components)
    if len(present) != 1:
        return NotProjectedContent(status="not_projected")
    key = present[0]
    if key not in _VALUE_KEYS:
        return NotProjectedContent(status="not_projected")
    projected = _project_value(key, resource.get(key))
    return projected if projected is not None else NotProjectedContent(status="not_projected")


class ClinicalReviewContextService:
    """Read current FHIR facts for one open review case. Eligibility is point-in-time."""

    def __init__(
        self,
        repository: FollowUpReviewCaseRepository,
        fhir_client: _ExactReadClient | None = None,
        *,
        fhir_client_factory: Callable[[], _ExactReadClient] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if (fhir_client is None) == (fhir_client_factory is None):
            raise ValueError("clinical review context requires one FHIR client source")
        self._repository = repository
        self._fhir = fhir_client
        self._fhir_client_factory = fhir_client_factory
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def read(self, review_case_id: str) -> ClinicalReviewContextResponse:
        try:
            case = self._repository.get(review_case_id)
        except ReviewPersistenceUnavailable:
            raise
        except Exception as exc:
            raise ClinicalContextUnavailable from exc
        if case is None:
            raise ReviewCaseNotFound
        if case.status is not ReviewCaseStatus.OPEN:
            raise ClinicalContextClosed
        if case.protocol_id == MISSED_FOLLOW_UP_REVIEW_V1:
            return self._read_missed_follow_up(case)
        encounter_id, observation_id = _provenance_ids(case)
        fhir = self._fhir_after_authorization()
        try:
            patient_id = _resolve_patient(fhir, case.case_id)
            encounter = _read_provenance(fhir, "Encounter", encounter_id)
            observation = _read_provenance(fhir, "Observation", observation_id)
            if isinstance(encounter, dict):
                _require_associated_encounter(encounter, encounter_id, patient_id)
            if isinstance(observation, dict):
                _require_associated_observation(observation, observation_id, encounter_id, patient_id)
            appointments = _read_appointments(fhir, patient_id, self._clock())
            return _response(case, encounter, observation, appointments, _retrieved_at(self._clock()))
        except ClinicalContextUnavailable:
            raise
        except Exception as exc:
            raise ClinicalContextUnavailable from exc

    def _read_missed_follow_up(self, case: FollowUpReviewCase) -> ClinicalReviewContextResponse:
        appointment_id = _missed_provenance_id(case)
        fhir = self._fhir_after_authorization()
        try:
            patient_id = _resolve_patient(fhir, case.case_id)
            appointment = _read_provenance(fhir, "Appointment", appointment_id)
            trigger_view = None
            if isinstance(appointment, dict):
                trigger_view = _require_associated_appointment(
                    appointment,
                    appointment_id,
                    patient_id,
                    self._clock(),
                )
            appointments = _read_appointments(fhir, patient_id, self._clock())
            return _missed_response(
                case,
                appointment_id,
                trigger_view,
                appointments,
                _retrieved_at(self._clock()),
            )
        except ClinicalContextUnavailable:
            raise
        except Exception as exc:
            raise ClinicalContextUnavailable from exc

    def _fhir_after_authorization(self) -> _ExactReadClient:
        """Build the FHIR client only after the open case and provenance are accepted."""
        if self._fhir is not None:
            return self._fhir
        factory = self._fhir_client_factory
        if factory is None:
            raise RuntimeError("clinical review context FHIR factory is missing")
        try:
            client = factory()
        except ReadClientError as exc:
            raise ClinicalContextUnavailable from exc
        if client is None:
            raise ClinicalContextUnavailable
        return client


def _missed_provenance_id(case: FollowUpReviewCase) -> str:
    if case.protocol_id != MISSED_FOLLOW_UP_REVIEW_V1:
        raise ClinicalContextUnavailable
    if case.protocol_evaluation_status != "matched":
        raise ClinicalContextUnavailable
    try:
        canonical_reason_codes(case.reason_codes)
    except Exception as exc:
        raise ClinicalContextUnavailable from exc
    if len(case.matched_resources) != 1:
        raise ClinicalContextUnavailable
    appointment_id = parse_fhir_reference(case.matched_resources[0], "Appointment")
    if appointment_id is None:
        raise ClinicalContextUnavailable
    return appointment_id


def _provenance_ids(case: FollowUpReviewCase) -> tuple[str, str]:
    if case.protocol_id != POST_CONSULTATION_RESULT_REVIEW_V1:
        raise ClinicalContextUnavailable
    if case.protocol_evaluation_status != "matched":
        raise ClinicalContextUnavailable
    try:
        canonical_reason_codes(case.reason_codes)
    except Exception as exc:
        raise ClinicalContextUnavailable from exc
    encounters: list[str] = []
    observations: list[str] = []
    if len(case.matched_resources) != 2:
        raise ClinicalContextUnavailable
    for reference in case.matched_resources:
        encounter_id = parse_fhir_reference(reference, "Encounter")
        observation_id = parse_fhir_reference(reference, "Observation")
        if encounter_id is not None and observation_id is None:
            encounters.append(encounter_id)
        elif observation_id is not None and encounter_id is None:
            observations.append(observation_id)
        else:
            raise ClinicalContextUnavailable
    if len(encounters) != 1 or len(observations) != 1:
        raise ClinicalContextUnavailable
    return encounters[0], observations[0]


def _resolve_patient(client: _ExactReadClient, case_id: str) -> str:
    result = client.search(case_resolution_search_path(case_id), "Patient")
    if result.status is not BoundedSearchStatus.COMPLETE:
        raise ClinicalContextUnavailable
    payload = {
        "resourceType": "Bundle",
        "type": "searchset",
        "entry": [{"resource": dict(item)} for item in result.resources],
    }
    try:
        return _patient_id_from_case_search(payload, case_id)
    except Exception as exc:
        raise ClinicalContextUnavailable from exc


def _read_provenance(client: _ExactReadClient, resource_type: str, resource_id: str) -> dict | None:
    try:
        payload = client.read_exact(resource_type, resource_id)
    except ExactResourceNotFound:
        return None
    except Exception as exc:
        raise ClinicalContextUnavailable from exc
    if not isinstance(payload, dict):
        raise ClinicalContextUnavailable
    return payload


def _require_associated_appointment(
    resource: dict,
    appointment_id: str,
    patient_id: str,
    now: datetime,
) -> dict:
    if resource.get("resourceType") != "Appointment" or resource.get("id") != appointment_id:
        raise ClinicalContextUnavailable
    try:
        view = _appointment_view(resource, patient_id, now)
    except Exception as exc:
        raise ClinicalContextUnavailable from exc
    if view is None or view.get("id") != appointment_id:
        raise ClinicalContextUnavailable
    if not isinstance(view.get("status"), str) or not _bounded_text(view["status"]):
        raise ClinicalContextUnavailable
    start = view.get("start")
    if start is not None and not _bounded_text(start):
        raise ClinicalContextUnavailable
    return view


def _require_associated_encounter(resource: dict, encounter_id: str, patient_id: str) -> None:
    if resource.get("resourceType") != "Encounter" or resource.get("id") != encounter_id:
        raise ClinicalContextUnavailable
    subject = resource.get("subject")
    reference = subject.get("reference") if isinstance(subject, dict) else None
    if parse_fhir_reference(reference, "Patient") != patient_id:
        raise ClinicalContextUnavailable
    _bounded_status(resource.get("status"))
    _bounded_period(resource.get("period"))


def _require_associated_observation(
    resource: dict,
    observation_id: str,
    encounter_id: str,
    patient_id: str,
) -> None:
    if resource.get("resourceType") != "Observation" or resource.get("id") != observation_id:
        raise ClinicalContextUnavailable
    subject = resource.get("subject")
    reference = subject.get("reference") if isinstance(subject, dict) else None
    if parse_fhir_reference(reference, "Patient") != patient_id:
        raise ClinicalContextUnavailable
    encounter = resource.get("encounter")
    encounter_reference = encounter.get("reference") if isinstance(encounter, dict) else None
    if parse_fhir_reference(encounter_reference, "Encounter") != encounter_id:
        raise ClinicalContextUnavailable
    _bounded_status(resource.get("status"))
    issued = resource.get("issued")
    if issued is not None and not _bounded_text(issued):
        raise ClinicalContextUnavailable


def _read_appointments(client: _ExactReadClient, patient_id: str, now: datetime) -> list[dict]:
    result = client.search(protocol_appointment_search_path(patient_id), "Appointment")
    if result.status is not BoundedSearchStatus.COMPLETE:
        raise ClinicalContextUnavailable
    views: list[dict] = []
    for resource in result.resources:
        if not isinstance(resource, dict):
            raise ClinicalContextUnavailable
        try:
            view = _appointment_view(resource, patient_id, now)
        except Exception as exc:
            raise ClinicalContextUnavailable from exc
        if view is None:
            raise ClinicalContextUnavailable
        if not isinstance(view.get("status"), str) or not _bounded_text(view["status"]):
            raise ClinicalContextUnavailable
        if view.get("classification") not in _ITEM_CLASSIFICATIONS:
            raise ClinicalContextUnavailable
        start = view.get("start")
        if start is not None and not _bounded_text(start):
            raise ClinicalContextUnavailable
        views.append(view)
    return views


def _response(
    case: FollowUpReviewCase,
    encounter: dict | None,
    observation: dict | None,
    appointments: list[dict],
    retrieved_at: str,
) -> ClinicalReviewContextResponse:
    encounter_id = parse_fhir_reference(
        next(item for item in case.matched_resources if item.startswith("Encounter/")),
        "Encounter",
    )
    observation_id = parse_fhir_reference(
        next(item for item in case.matched_resources if item.startswith("Observation/")),
        "Observation",
    )
    if encounter_id is None or observation_id is None:
        raise ClinicalContextUnavailable
    reasons: list[RetrievalReason] = []
    if encounter is None:
        reasons.append("provenance_encounter_not_found")
    if observation is None:
        reasons.append("provenance_observation_not_found")
    retrieval_status: Literal["complete", "provenance_resource_not_found"] = (
        "complete" if not reasons else "provenance_resource_not_found"
    )
    if not reasons:
        reasons = ["current_context_complete"]
    classified = schedule_classifications(appointments)
    return ClinicalReviewContextResponse(
        reviewCase=ReviewCaseRef(
            reviewCaseId=case.id,
            status="open",
            version=case.version,
        ),
        triggerProvenance=TriggerProvenance(
            protocolId=POST_CONSULTATION_RESULT_REVIEW_V1,
            evaluationStatus="matched",
            reasonCodes=list(case.reason_codes),
            matchedResources=list(case.matched_resources),
            createdAt=case.created_at,
        ),
        retrieval=RetrievalState(
            status=retrieval_status,
            retrievedAt=retrieved_at,
            source="fhir_current",
            reasonCodes=reasons,
        ),
        currentContext=CurrentContext(
            patient=PatientProjection(resolution="resolved"),
            encounter=_encounter_projection(encounter, encounter_id),
            observation=_observation_projection(observation, observation_id, encounter_id),
            appointments=AppointmentProjection(
                collectionStatus="complete",
                classifications=classified,
                items=[_appointment_item(item) for item in appointments],
            ),
        ),
    )


def _missed_response(
    case: FollowUpReviewCase,
    appointment_id: str,
    trigger_view: dict | None,
    appointments: list[dict],
    retrieved_at: str,
) -> ClinicalReviewContextResponse:
    reference = f"Appointment/{appointment_id}"
    reasons: list[RetrievalReason] = []
    if trigger_view is None:
        trigger: TriggerAppointmentAvailable | TriggerAppointmentMissing = TriggerAppointmentMissing(
            reference=reference,
            availability="not_found",
        )
        reasons.append("provenance_appointment_not_found")
    else:
        start = trigger_view.get("start")
        trigger = TriggerAppointmentAvailable(
            reference=reference,
            availability="available",
            status=str(trigger_view.get("status")),
            start=start if isinstance(start, str) else None,
        )
    retrieval_status: Literal["complete", "provenance_resource_not_found"] = (
        "complete" if not reasons else "provenance_resource_not_found"
    )
    if not reasons:
        reasons = ["current_context_complete"]
    return ClinicalReviewContextResponse(
        reviewCase=ReviewCaseRef(
            reviewCaseId=case.id,
            status="open",
            version=case.version,
        ),
        triggerProvenance=TriggerProvenance(
            protocolId=MISSED_FOLLOW_UP_REVIEW_V1,
            evaluationStatus="matched",
            reasonCodes=list(case.reason_codes),
            matchedResources=list(case.matched_resources),
            createdAt=case.created_at,
        ),
        retrieval=RetrievalState(
            status=retrieval_status,
            retrievedAt=retrieved_at,
            source="fhir_current",
            reasonCodes=reasons,
        ),
        currentContext=CurrentContext(
            patient=PatientProjection(resolution="resolved"),
            triggerAppointment=trigger,
            appointments=AppointmentProjection(
                collectionStatus="complete",
                classifications=schedule_classifications(appointments),
                items=[_appointment_item(item) for item in appointments],
            ),
        ),
    )


def _encounter_projection(resource: dict | None, encounter_id: str) -> EncounterAvailable | EncounterMissing:
    reference = f"Encounter/{encounter_id}"
    if resource is None:
        return EncounterMissing(reference=reference, availability="not_found")
    period = _period_projection(resource.get("period"))
    return EncounterAvailable(
        reference=reference,
        availability="available",
        status=str(resource.get("status")),
        period=period,
    )


def _observation_projection(
    resource: dict | None,
    observation_id: str,
    encounter_id: str,
) -> ObservationAvailable | ObservationMissing:
    reference = f"Observation/{observation_id}"
    if resource is None:
        return ObservationMissing(reference=reference, availability="not_found")
    issued = resource.get("issued")
    return ObservationAvailable(
        reference=reference,
        availability="available",
        status=str(resource.get("status")),
        issued=issued if isinstance(issued, str) else None,
        encounterReference=f"Encounter/{encounter_id}",
        code=project_observation_code(resource.get("code")),
        content=project_observation_content(resource),
    )


def _appointment_item(view: dict) -> AppointmentItem:
    return AppointmentItem(
        reference=f"Appointment/{view['id']}",
        status=view["status"],
        start=view.get("start") if isinstance(view.get("start"), str) else None,
        classification=view["classification"],
    )


def _project_coding(item: object) -> CodingEntry | None:
    if not isinstance(item, dict):
        return None
    system = item.get("system")
    code = item.get("code")
    display = item.get("display")
    if system is None and code is None and display is None:
        return None
    projected: dict[str, str] = {}
    for name, value in (("system", system), ("code", code), ("display", display)):
        if value is None:
            continue
        if not isinstance(value, str) or len(value) > MAX_TEXT:
            return None
        if not value.strip():
            continue
        projected[name] = value
    if not projected:
        return None
    return CodingEntry(**projected)


def _project_components(components: object) -> ObservationContent:
    if not isinstance(components, list) or len(components) > MAX_COMPONENTS or not components:
        return NotProjectedContent(status="not_projected")
    projected: list[ComponentContent] = []
    for component in components:
        if not isinstance(component, dict):
            return NotProjectedContent(status="not_projected")
        code = project_observation_code(component.get("code"))
        if code.status != "available":
            return NotProjectedContent(status="not_projected")
        value = project_observation_content(component)
        if not isinstance(value, NotProjectedContent) and value.kind == "components":
            return NotProjectedContent(status="not_projected")
        if isinstance(value, NotProjectedContent):
            return NotProjectedContent(status="not_projected")
        projected.append(ComponentContent(code=code, value=value))
    return ComponentsContent(status="available", kind="components", components=projected)


def _project_value(key: str, raw: object) -> ObservationContent | None:
    if key == "valueQuantity":
        quantity = _project_quantity(raw)
        if quantity is None:
            return None
        return QuantityContent(status="available", kind="quantity", **quantity.model_dump(exclude_none=True))
    if key == "valueCodeableConcept":
        code = project_observation_code(raw)
        if code.status != "available" or code.coding is None:
            return None
        return CodedContent(status="available", kind="coded", coding=code.coding, text=code.text)
    if key == "valueString":
        if not isinstance(raw, str) or not raw or len(raw) > MAX_TEXT:
            return None
        return StringContent(status="available", kind="string", value=raw)
    if key == "valueBoolean":
        if not isinstance(raw, bool):
            return None
        return BooleanContent(status="available", kind="boolean", value=raw)
    if key == "valueInteger":
        if isinstance(raw, bool) or not isinstance(raw, int) or raw < -(2**31) or raw > 2**31 - 1:
            return None
        return IntegerContent(status="available", kind="integer", value=raw)
    if key == "valueRange":
        return _project_range(raw)
    return None


def _project_quantity(raw: object) -> QuantityFields | None:
    if not isinstance(raw, dict) or "value" not in raw:
        return None
    value = raw.get("value")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if isinstance(value, float) and value != value or value in {float("inf"), float("-inf")}:
        return None
    comparator = raw.get("comparator")
    fields: dict[str, object] = {"value": value}
    if comparator is not None:
        if not isinstance(comparator, str) or comparator not in _COMPARATORS:
            return None
        fields["comparator"] = comparator
    for name in ("unit", "system", "code"):
        item = raw.get(name)
        if item is None:
            continue
        if not isinstance(item, str) or len(item) > MAX_TEXT:
            return None
        fields[name] = item
    return QuantityFields(**fields)


def _project_range(raw: object) -> RangeContent | None:
    if not isinstance(raw, dict):
        return None
    low = raw.get("low")
    high = raw.get("high")
    if low is None and high is None:
        return None
    projected_low = _project_quantity(low) if low is not None else None
    projected_high = _project_quantity(high) if high is not None else None
    if (low is not None and projected_low is None) or (high is not None and projected_high is None):
        return None
    if projected_low is None and projected_high is None:
        return None
    return RangeContent(status="available", kind="range", low=projected_low, high=projected_high)


def _bounded_status(value: object) -> None:
    if not isinstance(value, str) or not value or len(value) > 64 or any(char.isspace() for char in value):
        raise ClinicalContextUnavailable


def _bounded_text(value: object) -> bool:
    return isinstance(value, str) and bool(value) and len(value) <= MAX_TEXT


def _bounded_period(period: object) -> None:
    if period is None:
        return
    if not isinstance(period, dict):
        raise ClinicalContextUnavailable
    for name in ("start", "end"):
        value = period.get(name)
        if value is not None and not _bounded_text(value):
            raise ClinicalContextUnavailable


def _period_projection(period: object) -> EncounterPeriod | None:
    if not isinstance(period, dict):
        return None
    start = period.get("start") if _bounded_text(period.get("start")) else None
    end = period.get("end") if _bounded_text(period.get("end")) else None
    if start is None and end is None:
        return None
    return EncounterPeriod(start=start, end=end)


def _retrieved_at(now: datetime) -> str:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ClinicalContextUnavailable
    return now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
