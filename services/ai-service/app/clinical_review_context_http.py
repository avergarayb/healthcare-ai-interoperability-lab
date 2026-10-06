"""Authenticated HTTP adapter for current clinical review context."""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse, Response

from app.clinical_review_context import (
    ClinicalContextClosed,
    ClinicalContextUnavailable,
    ClinicalReviewContextService,
    dump_clinical_review_context,
)
from app.config import Settings
from app.followup_review import ReviewCaseNotFound, ReviewPersistenceUnavailable, validate_review_case_id
from app.followup_review_http import (
    INVALID_REVIEW_CASE_ID_DETAIL,
    NOT_FOUND_DETAIL,
    PERSISTENCE_UNAVAILABLE_DETAIL,
)
from app.langgraph_fhir_hapi import HapiReadClient
from app.service_auth import authenticate


CLINICAL_CONTEXT_UNAVAILABLE_DETAIL = "Clinical review context unavailable"
CLOSED_CONTEXT_DETAIL = "clinical_context_not_available_for_closed_case"


def get_clinical_review_context_http(
    request: Request,
    settings: Settings,
    review_case_id: str,
) -> Response:
    if not authenticate(request, settings):
        return Response(status_code=401)
    try:
        review_case_id = validate_review_case_id(review_case_id)
    except ValueError:
        return JSONResponse(status_code=422, content={"detail": INVALID_REVIEW_CASE_ID_DETAIL})
    repository = getattr(request.app.state, "followup_review_repository", None)
    if repository is None:
        return JSONResponse(status_code=503, content={"detail": PERSISTENCE_UNAVAILABLE_DETAIL})
    try:
        service = ClinicalReviewContextService(
            repository,
            fhir_client_factory=lambda: _fhir_client(request),
        )
        payload = service.read(review_case_id)
    except ReviewCaseNotFound:
        return JSONResponse(status_code=404, content={"detail": NOT_FOUND_DETAIL})
    except ClinicalContextClosed:
        return JSONResponse(status_code=409, content={"detail": CLOSED_CONTEXT_DETAIL})
    except ReviewPersistenceUnavailable:
        return JSONResponse(status_code=503, content={"detail": PERSISTENCE_UNAVAILABLE_DETAIL})
    except ClinicalContextUnavailable:
        return JSONResponse(status_code=503, content={"detail": CLINICAL_CONTEXT_UNAVAILABLE_DETAIL})
    return JSONResponse(status_code=200, content=dump_clinical_review_context(payload))


def _fhir_client(request: Request) -> HapiReadClient:
    factory = getattr(request.app.state, "clinical_context_fhir_client", None)
    if factory is not None:
        return factory()
    return HapiReadClient()
