"""Internal HTTP adapter for MISSED_FOLLOW_UP_REVIEW_V1.

Patient resolution and the bounded Appointment search are the existing
application reads. This path does not acquire Encounter or Observation
and does not call the narrative workflow.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Callable

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.followup_models import FollowUpRequest
from app.followup_review import (
    FollowUpReviewCase,
    FollowUpReviewCaseService,
    InvalidReviewTrigger,
    ReviewPersistenceUnavailable,
)
from app.config import Settings
from app.missed_follow_up_review import (
    MISSED_FOLLOW_UP_REVIEW_V1,
    REASON_MISSED,
    MissedFollowUpAppointment,
    MissedFollowUpEvaluation,
    MissedFollowUpSnapshot,
    evaluate_missed_follow_up,
)
from app.post_consultation_review import (
    CollectionState,
    ProtocolEvaluationStatus,
    ProtocolReviewResult,
)
from app.service_auth import authenticate

log = logging.getLogger("ai-service")

DISABLED_DETAIL = "Follow-up agent is disabled"
FAILED_DETAIL = "Missed follow-up review failed"
REVIEW_PERSISTENCE_UNAVAILABLE_DETAIL = "Follow-up review persistence unavailable"


class MissedFollowUpReviewCaseRef(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    review_case_id: str = Field(alias="reviewCaseId")
    status: str
    version: int = Field(ge=1)
    matched_resources: list[str] = Field(alias="matchedResources")


class MissedFollowUpResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    protocol_id: str = Field(alias="protocolId")
    case_id: str = Field(alias="caseId")
    evaluation_status: str = Field(alias="evaluationStatus")
    reason_codes: list[str] = Field(alias="reasonCodes")
    provenance_resources: list[str] = Field(alias="provenanceResources")
    review_cases: list[MissedFollowUpReviewCaseRef] = Field(alias="reviewCases")


def dump_missed_follow_up_response(response: MissedFollowUpResponse) -> dict:
    return response.model_dump(by_alias=True, mode="json", exclude_none=True)


def run_missed_follow_up_http(
    request: Request,
    settings: Settings,
    raw_body: bytes,
    *,
    adapter_factory: Callable[[datetime], Any] | None = None,
    clock: Callable[[], datetime] | None = None,
) -> Response:
    correlation_id = request.headers.get("X-Correlation-ID") or "missing"
    if not authenticate(request, settings):
        _log(correlation_id, "UNAUTHORIZED")
        return Response(status_code=401)
    if not settings.followup_agent_enabled:
        _log(correlation_id, "DISABLED")
        return JSONResponse(status_code=503, content={"detail": DISABLED_DETAIL})
    try:
        parsed = FollowUpRequest.model_validate(_load_body(raw_body))
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc

    instant = (clock or _utc_now)()
    factory = adapter_factory or _live_adapter
    try:
        adapter = factory(instant)
        evaluation = evaluate_missed_follow_up_case(adapter, parsed.case_id, instant)
        review_cases = _ensure_review_cases(request, parsed.case_id, evaluation)
        payload = _project(parsed.case_id, evaluation, review_cases)
    except (ReviewPersistenceUnavailable, InvalidReviewTrigger):
        _log(correlation_id, "persistence_unavailable")
        return JSONResponse(status_code=503, content={"detail": REVIEW_PERSISTENCE_UNAVAILABLE_DETAIL})
    except Exception:
        _log(correlation_id, "error")
        return JSONResponse(status_code=502, content={"detail": FAILED_DETAIL})
    if payload is None:
        _log(correlation_id, "error")
        return JSONResponse(status_code=502, content={"detail": FAILED_DETAIL})
    _log(correlation_id, payload.evaluation_status)
    return JSONResponse(status_code=200, content=dump_missed_follow_up_response(payload))


def evaluate_missed_follow_up_case(adapter: Any, case_id: str, instant: datetime) -> MissedFollowUpEvaluation:
    """Resolve the authorized Patient, read Appointments, and evaluate once."""
    with adapter.bind_read(case_id):
        snapshot = _read_snapshot(adapter, instant)
    return evaluate_missed_follow_up(snapshot)


def _read_snapshot(adapter: Any, instant: datetime) -> MissedFollowUpSnapshot:
    from app.langgraph_fhir_client import ReadClientError
    from app.langgraph_fhir_followup import _IncompleteProtocolRead, _parsed_start

    case_id = adapter._scope().case_id
    try:
        patient_id = adapter.resolve_patient_for_protocol(case_id)
    except _IncompleteProtocolRead:
        return _snapshot(adapter, instant, _parsed_start)
    except ReadClientError:
        if adapter.ledger.patient_collection is CollectionState.NOT_READ:
            adapter.ledger.patient_collection = CollectionState.UNAVAILABLE
            adapter.ledger.acquisition_reason_codes = ("patient_resolution_unavailable",)
            adapter.record_patient_search_failure(ReadClientError("patient resolution unavailable"))
        return _snapshot(adapter, instant, _parsed_start)
    try:
        patient = adapter.get_patient(patient_id)
    except ReadClientError:
        adapter.ledger.patient_collection = CollectionState.UNAVAILABLE
        adapter.ledger.acquisition_reason_codes = ("patient_read_unavailable",)
        adapter.record_patient_read_failure()
        return _snapshot(adapter, instant, _parsed_start)
    adapter.record_patient_resolved(patient)
    try:
        adapter.search_appointments_for_protocol(patient_id)
    except ReadClientError:
        return _snapshot(adapter, instant, _parsed_start)
    return _snapshot(adapter, instant, _parsed_start)


def _snapshot(adapter: Any, instant: datetime, parse_start: Callable[[object], datetime | None]) -> MissedFollowUpSnapshot:
    appointments: list[MissedFollowUpAppointment] = []
    for view in adapter.ledger.appointment_views:
        if not isinstance(view, dict):
            continue
        appointment_id = view.get("id")
        if not isinstance(appointment_id, str) or not appointment_id:
            continue
        status = view.get("status")
        start_raw = view.get("start")
        appointments.append(
            MissedFollowUpAppointment(
                reference=f"Appointment/{appointment_id}",
                appointment_id=appointment_id,
                status=status if isinstance(status, str) else "",
                start=parse_start(start_raw) if isinstance(start_raw, str) else None,
            )
        )
    return MissedFollowUpSnapshot(
        patient_id=adapter.ledger.patient_id,
        patient_state=adapter.ledger.patient_collection,
        appointment_state=adapter.ledger.appointment_collection,
        appointments=tuple(appointments),
        acquisition_reason_codes=tuple(adapter.ledger.acquisition_reason_codes),
        evaluated_at=instant,
    )


def _ensure_review_cases(
    request: Request,
    case_id: str,
    evaluation: MissedFollowUpEvaluation,
) -> tuple[FollowUpReviewCase, ...]:
    if evaluation.status is not ProtocolEvaluationStatus.MATCHED:
        return ()
    repository = getattr(request.app.state, "followup_review_repository", None)
    if repository is None:
        raise ReviewPersistenceUnavailable
    service = FollowUpReviewCaseService(repository)
    cases: list[FollowUpReviewCase] = []
    for reference in evaluation.triggers:
        protocol = ProtocolReviewResult(
            id=MISSED_FOLLOW_UP_REVIEW_V1,
            evaluation_status=ProtocolEvaluationStatus.MATCHED,
            reason_codes=(REASON_MISSED,),
            matched_resources=(reference,),
            human_review_status="required",
            human_review_reason="deterministic_missed_follow_up_protocol_match",
            action_status="proposed",
            action_type="review_follow_up_case",
        )
        case = service.ensure_for_protocol(case_id, protocol)
        if case is None:
            raise ReviewPersistenceUnavailable
        cases.append(case)
    return tuple(cases)


def _project(
    case_id: str,
    evaluation: MissedFollowUpEvaluation,
    review_cases: tuple[FollowUpReviewCase, ...],
) -> MissedFollowUpResponse | None:
    try:
        return MissedFollowUpResponse(
            protocolId=MISSED_FOLLOW_UP_REVIEW_V1,
            caseId=case_id,
            evaluationStatus=evaluation.status.value,
            reasonCodes=list(evaluation.reason_codes),
            provenanceResources=list(evaluation.provenance_resources),
            reviewCases=[
                MissedFollowUpReviewCaseRef(
                    reviewCaseId=case.id,
                    status=case.status.value,
                    version=case.version,
                    matchedResources=list(case.matched_resources),
                )
                for case in review_cases
            ],
        )
    except ValidationError:
        return None


def _live_adapter(instant: datetime):
    from app.langgraph_fhir_client import ClientFHIRTransport
    from app.langgraph_fhir_followup import FollowUpFHIRAdapter
    from app.langgraph_fhir_hapi import HapiReadClient

    return FollowUpFHIRAdapter(ClientFHIRTransport(HapiReadClient()), now=lambda: instant)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _load_body(raw: bytes) -> Any:
    if raw is None or raw.strip() == b"":
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def _log(correlation_id: str, status: str) -> None:
    line = (
        f"missed_follow_up correlationId={correlation_id} method=POST "
        f"path=/internal/agent/missed-follow-up status={status}"
    )
    lowered = line.lower()
    if "x-service-token=" in lowered or "signing_secret=" in lowered:
        raise RuntimeError("missed follow-up log line must not contain secrets")
    log.info(line)
