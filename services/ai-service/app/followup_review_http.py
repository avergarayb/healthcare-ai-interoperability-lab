"""Authenticated internal HTTP adapter for durable follow-up review cases."""

from __future__ import annotations

import json
from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.config import Settings
from app.followup_review import (
    FollowUpReviewCase,
    FollowUpReviewCaseEvent,
    FollowUpReviewCaseService,
    ReviewCaseConflict,
    ReviewCaseNotFound,
    ReviewCaseStatus,
    ReviewOutcome,
    ReviewPersistenceUnavailable,
    decode_cursor,
    encode_cursor,
    validate_review_case_id,
)
from app.service_auth import authenticate


PERSISTENCE_UNAVAILABLE_DETAIL = "Follow-up review persistence unavailable"
INVALID_REVIEW_CASE_ID_DETAIL = "Invalid review case id"
INVALID_CURSOR_DETAIL = "Invalid review case cursor"
CONFLICT_DETAIL = "Follow-up review case conflict"
NOT_FOUND_DETAIL = "Follow-up review case not found"


class ReviewCaseSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    review_case_id: str = Field(alias="reviewCaseId")
    case_id: str = Field(alias="caseId")
    protocol_id: str = Field(alias="protocolId")
    status: ReviewCaseStatus
    outcome: ReviewOutcome | None = None
    version: int
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")
    closed_at: str | None = Field(default=None, alias="closedAt")


class ReviewTransitionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    event_id: str = Field(alias="eventId")
    case_version: int = Field(alias="caseVersion")
    event_type: str = Field(alias="eventType")
    from_status: ReviewCaseStatus | None = Field(default=None, alias="fromStatus")
    to_status: ReviewCaseStatus = Field(alias="toStatus")
    outcome: ReviewOutcome | None = None
    occurred_at: str = Field(alias="occurredAt")


class ReviewCaseDetailResponse(ReviewCaseSummaryResponse):
    protocol_evaluation_status: str = Field(alias="protocolEvaluationStatus")
    reason_codes: list[str] = Field(alias="reasonCodes")
    matched_resources: list[str] = Field(alias="matchedResources")
    transitions: list[ReviewTransitionResponse]


class ReviewCaseListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    items: list[ReviewCaseSummaryResponse]
    next_cursor: str | None = Field(default=None, alias="nextCursor")


class CloseReviewCaseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    expected_version: int = Field(alias="expectedVersion", ge=1)
    outcome: ReviewOutcome


class ReviewQueueQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    status: ReviewCaseStatus = ReviewCaseStatus.OPEN
    case_id: str | None = Field(default=None, alias="caseId", min_length=1, max_length=255)
    limit: int = Field(default=25, ge=1, le=100)
    cursor: str | None = Field(default=None, max_length=2048)


def list_review_cases_http(request: Request, settings: Settings) -> Response:
    if not authenticate(request, settings):
        return Response(status_code=401)
    try:
        query = ReviewQueueQuery.model_validate(_query_values(request))
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc
    try:
        after = (
            decode_cursor(query.cursor, status=query.status, case_id=query.case_id)
            if query.cursor is not None
            else None
        )
    except ValueError:
        return JSONResponse(status_code=422, content={"detail": INVALID_CURSOR_DETAIL})
    try:
        service = _service(request)
        page = service.list_cases(
            status=query.status,
            case_id=query.case_id,
            limit=query.limit,
            after=after,
        )
    except ReviewPersistenceUnavailable:
        return _persistence_unavailable()
    next_cursor = (
        encode_cursor(page.next_position, status=query.status, case_id=query.case_id)
        if page.next_position is not None
        else None
    )
    payload = ReviewCaseListResponse(
        items=[_summary(item) for item in page.items],
        nextCursor=next_cursor,
    )
    return JSONResponse(status_code=200, content=_dump(payload))


def get_review_case_http(request: Request, settings: Settings, review_case_id: str) -> Response:
    if not authenticate(request, settings):
        return Response(status_code=401)
    try:
        review_case_id = validate_review_case_id(review_case_id)
    except ValueError:
        return JSONResponse(status_code=422, content={"detail": INVALID_REVIEW_CASE_ID_DETAIL})
    try:
        service = _service(request)
        detail = service.detail(review_case_id)
    except ReviewCaseNotFound:
        return JSONResponse(status_code=404, content={"detail": NOT_FOUND_DETAIL})
    except ReviewPersistenceUnavailable:
        return _persistence_unavailable()
    return JSONResponse(status_code=200, content=_dump(_detail(detail.case, detail.events)))


def close_review_case_http(
    request: Request,
    settings: Settings,
    review_case_id: str,
    raw_body: bytes,
) -> Response:
    if not authenticate(request, settings):
        return Response(status_code=401)
    try:
        review_case_id = validate_review_case_id(review_case_id)
    except ValueError:
        return JSONResponse(status_code=422, content={"detail": INVALID_REVIEW_CASE_ID_DETAIL})
    try:
        body = CloseReviewCaseRequest.model_validate(_load_json(raw_body))
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc
    try:
        service = _service(request)
        case = service.close(
            review_case_id,
            expected_version=body.expected_version,
            outcome=body.outcome,
        )
        detail = service.detail(review_case_id)
    except ReviewCaseNotFound:
        return JSONResponse(status_code=404, content={"detail": NOT_FOUND_DETAIL})
    except ReviewCaseConflict:
        return JSONResponse(status_code=409, content={"detail": CONFLICT_DETAIL})
    except ReviewPersistenceUnavailable:
        return _persistence_unavailable()
    return JSONResponse(status_code=200, content=_dump(_detail(detail.case, detail.events)))


def _service(request: Request) -> FollowUpReviewCaseService:
    repository = getattr(request.app.state, "followup_review_repository", None)
    if repository is None:
        raise ReviewPersistenceUnavailable
    return FollowUpReviewCaseService(repository)


def _query_values(request: Request) -> dict[str, str]:
    values: dict[str, str] = {}
    for name, value in request.query_params.multi_items():
        if name in values:
            raise RequestValidationError(
                [{"type": "value_error", "loc": ("query", name), "msg": "duplicate query parameter", "input": value}]
            )
        values[name] = value
    return values


def _load_json(raw_body: bytes) -> Any:
    try:
        return json.loads(raw_body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RequestValidationError(
            [{"type": "json_invalid", "loc": ("body",), "msg": "Invalid JSON", "input": None}]
        ) from exc


def _summary(case: FollowUpReviewCase) -> ReviewCaseSummaryResponse:
    return ReviewCaseSummaryResponse(
        reviewCaseId=case.id,
        caseId=case.case_id,
        protocolId=case.protocol_id,
        status=case.status,
        outcome=case.outcome,
        version=case.version,
        createdAt=case.created_at,
        updatedAt=case.updated_at,
        closedAt=case.closed_at,
    )


def _detail(
    case: FollowUpReviewCase,
    events: tuple[FollowUpReviewCaseEvent, ...],
) -> ReviewCaseDetailResponse:
    summary = _summary(case).model_dump(by_alias=True)
    return ReviewCaseDetailResponse(
        **summary,
        protocolEvaluationStatus=case.protocol_evaluation_status,
        reasonCodes=list(case.reason_codes),
        matchedResources=list(case.matched_resources),
        transitions=[
            ReviewTransitionResponse(
                eventId=event.event_id,
                caseVersion=event.case_version,
                eventType=event.event_type.value,
                fromStatus=event.from_status,
                toStatus=event.to_status,
                outcome=event.outcome,
                occurredAt=event.occurred_at,
            )
            for event in events
        ],
    )


def _dump(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(by_alias=True, mode="json", exclude_none=True)


def _persistence_unavailable() -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": PERSISTENCE_UNAVAILABLE_DETAIL})
