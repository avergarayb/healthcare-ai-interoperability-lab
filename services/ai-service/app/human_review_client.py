"""Server-rendered synthetic review demo inside Healthcare AI.

The browser receives HTML only. It does not receive the service credential.
This module presents durable review state and the existing current-context
projection. It does not evaluate a protocol, classify appointments, or store
the projection.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import re
import secrets
import threading
import time
import uuid
from html import escape
from urllib.parse import parse_qsl, quote

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from app.human_attribution import (
    COORDINATION_REQUEST_CREATED,
    REVIEW_CASE_CLOSED,
    DevelopmentPrincipalSnapshot,
    StoredDevelopmentAttribution,
)
from app.human_development_auth import require_human_session

from app.clinical_review_context import (
    ClinicalContextClosed,
    ClinicalContextUnavailable,
    ClinicalReviewContextResponse,
    CodedContent,
    ComponentsContent,
    IntegerContent,
    NotProjectedContent,
    ObservationCode,
    QuantityContent,
    QuantityFields,
    RangeContent,
    StringContent,
    BooleanContent,
)
from app.ai_assisted_review import (
    AssistanceResult,
    generate_ai_assistance,
    render_assistance_section,
    resolve_assistance_provider,
)
from app.clinical_review_context_http import clinical_context_service
from app.config import Settings
from app.institutional_knowledge import UnavailableInstitutionalKnowledge
from app.followup_coordination_action import (
    PERSISTABLE_PROTOCOL_IDS,
    CoordinationActionDenied,
    CoordinationActionType,
    FollowUpCoordinationActionService,
    FollowUpCoordinationRequest,
)
from app.followup_review import (
    FollowUpReviewCase,
    FollowUpReviewCaseEvent,
    FollowUpReviewCaseService,
    ReviewCaseConflict,
    ReviewCaseDetail,
    ReviewCaseNotFound,
    ReviewCaseStatus,
    ReviewOutcome,
    ReviewPersistenceUnavailable,
    decode_cursor,
    encode_cursor,
    validate_review_case_id,
)

log = logging.getLogger("ai-service.human-review")

QUEUE_LIMIT = 25
FORM_TTL_SECONDS = 900
_CORRELATION = re.compile(r"^[A-Za-z0-9._:-]{1,64}$")

_SENTENCE_PENDING = "Coordinación interna planificada. Solicitud pendiente de registro."
_SENTENCE_RECORDED = "Solicitud interna de coordinación registrada."
_SENTENCE_NO_ACTION = "Revisión finalizada sin acción operativa registrada."
_SENTENCE_NO_EXTERNAL = "Esto no envía un mensaje, no escribe FHIR y no agenda una cita."
_RULE_MATCHED = (
    "La regla operativa de revisión se cumplió. Esto no es un diagnóstico ni una recomendación clínica."
)
_HISTORY_OUTCOMES = {
    ReviewOutcome.FOLLOW_UP_COORDINATION_PLANNED: "Coordinación interna planificada",
    ReviewOutcome.REVIEW_COMPLETED_NO_OPERATIONAL_ACTION: "Sin acción operativa registrada",
}
_PROTOCOL_LABELS = {
    "POST_CONSULTATION_RESULT_REVIEW_V1": "Revisión de un resultado posterior a la consulta",
    "MISSED_FOLLOW_UP_REVIEW_V1": "Revisión de un seguimiento no realizado",
}
_PAGE_REASONS = {
    "post_consultation_result_requires_review": (
        "Quedó registrado un resultado posterior a la consulta y el caso se abrió para revisión humana."
    ),
    "missed_follow_up_without_confirmed_replacement": (
        "La cita de seguimiento no se completó y, al crear el caso, no había otra cita futura confirmada."
    ),
}
_APPOINTMENT_LABELS = {
    "NONE": "No se obtuvo ninguna cita.",
    "UPCOMING_CONFIRMED": "Próxima y confirmada",
    "UPCOMING_UNCONFIRMED": "Próxima y no confirmada",
    "CANCELLED": "Cancelada",
    "PAST": "Pasada",
    "OTHER": "Estado operativo de la cita no clasificado",
}
_ORIGIN_APPOINTMENT = "Cita que originó el caso"
_ORIGIN_POINTER = "La cita que originó este caso está arriba."
_MONTHS = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)
_REVIEW_TIMESTAMP = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})\.\d{6}Z$"
)

MSG_EMPTY = "No hay casos de revisión abiertos."
MSG_CURSOR = "This page link is no longer valid."
MSG_REVIEW_UNAVAILABLE = "Review service is unavailable."
MSG_NOT_FOUND = "This review case was not found."
MSG_INVALID_LINK = "This review link is not valid."
MSG_CONTEXT_UNAVAILABLE = "El contexto clínico actual no está disponible en este momento."
MSG_CONTEXT_CLOSED = "El contexto clínico actual no se muestra cuando el caso está cerrado."
MSG_ENCOUNTER_MISSING = "The recorded encounter was not found."
MSG_OBSERVATION_MISSING = "The recorded observation was not found."
MSG_APPOINTMENT_MISSING = "The recorded appointment was not found."
MSG_VALUE_HIDDEN = "Result value is not available in this view."
MSG_CODE_HIDDEN = "Result code is not available in this view."
MSG_CLOSE_INVALID = "The close request was not valid."
MSG_FORM_INVALID = "This close form is no longer valid."
MSG_ORIGIN_INVALID = "This close form was not sent from this demo."
MSG_ASSISTANCE_REQUEST_INVALID = "This AI assistance request was not valid."
MSG_ASSISTANCE_TOKEN_INVALID = "This AI assistance request is no longer valid."
MSG_ASSISTANCE_ORIGIN_INVALID = "This AI assistance request was not sent from this demo."
MSG_ACTION_INVALID = "This coordination request was not valid."
MSG_ACTION_TOKEN_INVALID = "This coordination request is no longer valid."
MSG_ACTION_ORIGIN_INVALID = "This coordination request was not sent from this demo."
MSG_ACTION_DENIED = "This coordination request cannot be created."
MSG_NOT_CONFIGURED = "This demo is not configured."
MSG_CHANGED = "This case changed. Review the current version before closing."
MSG_CONTEXT_SCOPE = (
    "El contexto clínico actual es una lectura de ahora. No vuelve a ejecutar la regla que creó el caso."
)
MSG_CLOSE_SCOPE = (
    "Esto registra un resultado operativo de la revisión. No es un diagnóstico ni una decisión de tratamiento."
)
MSG_DEMO = (
    "Demostración sintética de laboratorio. Estas páginas exigen una sesión de desarrollo. "
    "Esa sesión no es una identidad clínica verificada, ni IAM, ni SSO, ni acceso por roles. "
    "El identificador del caso es operativo y no es la identidad del paciente."
)
MSG_PATIENT_HIDDEN = "La identidad del paciente no se muestra."
_HANDOFF_COOKIE = "ai_assistance_once"
_HANDOFF_TTL_SECONDS = 60


class _AssistanceHandoff:
    """One-time process memory so a 303 can show assistance without storing it."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: dict[str, tuple[str, AssistanceResult, float]] = {}

    def put(self, review_case_id: str, result: AssistanceResult) -> str:
        token = secrets.token_urlsafe(32)
        expires = time.monotonic() + _HANDOFF_TTL_SECONDS
        with self._lock:
            self._drop_expired(time.monotonic())
            self._items[token] = (review_case_id, result, expires)
        return token

    def take(self, token: str, review_case_id: str) -> AssistanceResult | None:
        now = time.monotonic()
        with self._lock:
            self._drop_expired(now)
            item = self._items.get(token)
            if item is None:
                return None
            stored_case, result, expires = item
            if expires <= now or stored_case != review_case_id:
                return None
            del self._items[token]
            return result

    def _drop_expired(self, now: float) -> None:
        expired = [key for key, item in self._items.items() if item[2] <= now]
        for key in expired:
            del self._items[key]


_ASSISTANCE_HANDOFF = _AssistanceHandoff()


def issue_form_token(
    *,
    secret: str,
    review_case_id: str,
    expected_version: int,
    session_id: str,
    now: int | None = None,
) -> tuple[str, int] | None:
    """Sign the close parameters for a short window. Returns None without a server secret."""
    if not secret:
        return None
    issued_at = _now() if now is None else now
    expiry = issued_at + FORM_TTL_SECONDS
    return _sign(secret, review_case_id, expected_version, expiry, session_id), expiry


def form_token_is_valid(
    *,
    secret: str,
    review_case_id: str,
    expected_version: int,
    expiry: int,
    token: str,
    session_id: str,
    now: int | None = None,
) -> bool:
    """Check that this presentation layer issued the submitted case, version and expiry."""
    if not secret or not token:
        return False
    current = _now() if now is None else now
    if expiry > current + FORM_TTL_SECONDS or current >= expiry:
        return False
    expected = _sign(secret, review_case_id, expected_version, expiry, session_id)
    try:
        return hmac.compare_digest(expected, token)
    except TypeError:
        return False


def issue_assistance_token(
    *,
    secret: str,
    review_case_id: str,
    session_id: str,
    now: int | None = None,
) -> tuple[str, int] | None:
    """Sign an AI-assistance request. The purpose is not a close-form signature."""
    if not secret:
        return None
    issued_at = _now() if now is None else now
    expiry = issued_at + FORM_TTL_SECONDS
    return _sign_assistance(secret, review_case_id, expiry, session_id), expiry


def assistance_token_is_valid(
    *,
    secret: str,
    review_case_id: str,
    expiry: int,
    token: str,
    session_id: str,
    now: int | None = None,
) -> bool:
    """Accept only an AI-assistance signature for this case and expiry."""
    if not secret or not token:
        return False
    current = _now() if now is None else now
    if expiry > current + FORM_TTL_SECONDS or current >= expiry:
        return False
    expected = _sign_assistance(secret, review_case_id, expiry, session_id)
    try:
        return hmac.compare_digest(expected, token)
    except TypeError:
        return False


def issue_controlled_action_token(
    *,
    secret: str,
    review_case_id: str,
    session_id: str,
    now: int | None = None,
) -> tuple[str, int] | None:
    """Sign a controlled-action request. The purpose is not a close or assistance signature."""
    if not secret:
        return None
    issued_at = _now() if now is None else now
    expiry = issued_at + FORM_TTL_SECONDS
    return _sign_controlled_action(secret, review_case_id, expiry, session_id), expiry


def controlled_action_token_is_valid(
    *,
    secret: str,
    review_case_id: str,
    expiry: int,
    token: str,
    session_id: str,
    now: int | None = None,
) -> bool:
    """Accept only a controlled-action signature for this case, action and expiry."""
    if not secret or not token:
        return False
    current = _now() if now is None else now
    if expiry > current + FORM_TTL_SECONDS or current >= expiry:
        return False
    expected = _sign_controlled_action(secret, review_case_id, expiry, session_id)
    try:
        return hmac.compare_digest(expected, token)
    except TypeError:
        return False


def render_review_queue(request: Request, settings: Settings) -> Response:
    started = time.perf_counter()
    status = 200
    try:
        session = require_human_session(request, settings)
        if isinstance(session, Response):
            status = session.status_code
            return session
        cursor = request.query_params.get("cursor")
        if len(request.query_params.getlist("cursor")) > 1:
            status = 422
            return _html(_page("Review queue", _error(MSG_CURSOR) + _queue_home()), status)
        repository = _repository(request)
        if repository is None:
            status = 503
            return _html(_page("Review queue", _error(MSG_REVIEW_UNAVAILABLE)), status)
        try:
            after = (
                decode_cursor(cursor, status=ReviewCaseStatus.OPEN, case_id=None)
                if cursor
                else None
            )
        except ValueError:
            status = 422
            return _html(_page("Review queue", _error(MSG_CURSOR) + _queue_home()), status)
        try:
            page = FollowUpReviewCaseService(repository).list_cases(
                status=ReviewCaseStatus.OPEN,
                case_id=None,
                limit=QUEUE_LIMIT,
                after=after,
            )
        except ReviewPersistenceUnavailable:
            status = 503
            return _html(_page("Review queue", _error(MSG_REVIEW_UNAVAILABLE)), status)
        return _html(_page("Casos abiertos", _queue_body(page.items, page.next_position)))
    finally:
        _log(request, "/review-cases", status, started)


def render_review_case(request: Request, settings: Settings, review_case_id: str) -> Response:
    started = time.perf_counter()
    status = 200
    try:
        session = require_human_session(request, settings)
        if isinstance(session, Response):
            status = session.status_code
            return session
        try:
            review_case_id = validate_review_case_id(review_case_id)
        except ValueError:
            status = 422
            return _html(_page("Review case", _error(MSG_INVALID_LINK) + _queue_home()), status)
        detail, failure = _load_detail(request, review_case_id)
        if failure is not None:
            status = failure
            message = MSG_NOT_FOUND if failure == 404 else MSG_REVIEW_UNAVAILABLE
            return _html(_page("Review case", _error(message) + _queue_home()), status)
        assert detail is not None
        coordination, coordination_failure = _load_coordination_request(request, review_case_id)
        if coordination_failure is not None:
            status = coordination_failure
            return _html(_page("Review case", _error(MSG_REVIEW_UNAVAILABLE) + _queue_home()), status)
        attributions, attribution_failure = _load_human_attributions(request, review_case_id)
        if attribution_failure is not None:
            status = attribution_failure
            return _html(_page("Review case", _error(MSG_REVIEW_UNAVAILABLE) + _queue_home()), status)
        notice = MSG_CHANGED if request.query_params.get("notice") == "changed" else ""
        context, context_message = _load_context(request, detail.case)
        ticket = request.cookies.get(_HANDOFF_COOKIE)
        assistance = _ASSISTANCE_HANDOFF.take(ticket, review_case_id) if ticket else None
        body = _case_body(
            detail,
            context,
            context_message,
            settings,
            notice,
            assistance=assistance,
            coordination=coordination,
            attributions=attributions,
            session_id=session.session_id,
        )
        response = _html(_page("Caso de revisión", body))
        response.delete_cookie(_HANDOFF_COOKIE, path=_handoff_path(review_case_id))
        return response
    finally:
        _log(request, "/review-cases/{reviewCaseId}", status, started, review_case_id)


def close_review_case(
    request: Request,
    settings: Settings,
    review_case_id: str,
    raw_body: bytes,
    content_type: str | None,
) -> Response:
    started = time.perf_counter()
    status = 400
    try:
        session = require_human_session(request, settings)
        if isinstance(session, Response):
            status = session.status_code
            return session
        try:
            review_case_id = validate_review_case_id(review_case_id)
        except ValueError:
            status = 422
            return _html(_page("Review case", _error(MSG_INVALID_LINK) + _queue_home()), status)
        if not _same_origin(request):
            return _html(_page("Review case", _error(MSG_ORIGIN_INVALID) + _queue_home()), status)
        fields = _form_fields(raw_body, content_type)
        if fields is None:
            return _html(_page("Review case", _error(MSG_CLOSE_INVALID) + _queue_home()), status)
        outcome = _outcome(fields.get("outcome"))
        version = _version(fields.get("expectedVersion"))
        expiry = _expiry(fields.get("formExpiry"))
        token = fields.get("formToken", "")
        if outcome is None or version is None or expiry is None:
            return _html(_page("Review case", _error(MSG_CLOSE_INVALID) + _queue_home()), status)
        if not settings.human_review_form_signing_secret:
            return _html(_page("Review case", _error(MSG_NOT_CONFIGURED) + _queue_home()), status)
        if not form_token_is_valid(
            secret=settings.human_review_form_signing_secret,
            review_case_id=review_case_id,
            expected_version=version,
            expiry=expiry,
            token=token,
            session_id=session.session_id,
        ):
            return _html(_page("Review case", _error(MSG_FORM_INVALID) + _queue_home()), status)
        repository = _repository(request)
        if repository is None:
            status = 503
            return _html(_page("Review case", _error(MSG_REVIEW_UNAVAILABLE) + _queue_home()), status)
        try:
            attribution = _snapshot_from_session(session)
        except ValueError:
            status = 503
            return _html(_page("Review case", _error(MSG_REVIEW_UNAVAILABLE) + _queue_home()), status)
        service = FollowUpReviewCaseService(repository)
        try:
            service.close(
                review_case_id,
                expected_version=version,
                outcome=outcome,
                attribution=attribution,
            )
        except ReviewCaseNotFound:
            status = 404
            return _html(_page("Review case", _error(MSG_NOT_FOUND) + _queue_home()), status)
        except ReviewPersistenceUnavailable:
            status = 503
            return _html(_page("Review case", _error(MSG_REVIEW_UNAVAILABLE) + _queue_home()), status)
        except ReviewCaseConflict:
            try:
                detail = service.detail(review_case_id)
            except ReviewCaseNotFound:
                status = 404
                return _html(_page("Review case", _error(MSG_NOT_FOUND) + _queue_home()), status)
            except ReviewPersistenceUnavailable:
                status = 503
                return _html(_page("Review case", _error(MSG_REVIEW_UNAVAILABLE) + _queue_home()), status)
            status = 303
            if detail.case.status is ReviewCaseStatus.CLOSED:
                return _redirect(review_case_id)
            return _redirect(review_case_id, notice=True)
        status = 303
        return _redirect(review_case_id)
    finally:
        _log(request, "/review-cases/{reviewCaseId}/close", status, started, review_case_id)


def submit_ai_assistance(
    request: Request,
    settings: Settings,
    review_case_id: str,
    raw_body: bytes,
    content_type: str | None,
) -> Response:
    started = time.perf_counter()
    status = 400
    try:
        session = require_human_session(request, settings)
        if isinstance(session, Response):
            status = session.status_code
            return session
        try:
            review_case_id = validate_review_case_id(review_case_id)
        except ValueError:
            status = 422
            return _html(_page("Review case", _error(MSG_INVALID_LINK) + _queue_home()), status)
        if not _same_origin(request):
            return _html(_page("Review case", _error(MSG_ASSISTANCE_ORIGIN_INVALID) + _queue_home()), status)
        fields = _assistance_form_fields(raw_body, content_type)
        if fields is None:
            return _html(_page("Review case", _error(MSG_ASSISTANCE_REQUEST_INVALID) + _queue_home()), status)
        expiry = _expiry(fields.get("assistanceExpiry"))
        token = fields.get("assistanceToken", "")
        if expiry is None:
            return _html(_page("Review case", _error(MSG_ASSISTANCE_REQUEST_INVALID) + _queue_home()), status)
        if not settings.human_review_form_signing_secret:
            return _html(_page("Review case", _error(MSG_NOT_CONFIGURED) + _queue_home()), status)
        if not assistance_token_is_valid(
            secret=settings.human_review_form_signing_secret,
            review_case_id=review_case_id,
            expiry=expiry,
            token=token,
            session_id=session.session_id,
        ):
            return _html(_page("Review case", _error(MSG_ASSISTANCE_TOKEN_INVALID) + _queue_home()), status)
        detail, failure = _load_detail(request, review_case_id)
        if failure is not None:
            status = failure
            message = MSG_NOT_FOUND if failure == 404 else MSG_REVIEW_UNAVAILABLE
            return _html(_page("Review case", _error(message) + _queue_home()), status)
        assert detail is not None
        if detail.case.status is not ReviewCaseStatus.OPEN:
            status = 409
            return _html(
                _page("Review case", _error("AI assistance is available only for an open review case.") + _queue_home()),
                status,
            )
        repository = _repository(request)
        if repository is None:
            status = 503
            return _html(_page("Review case", _error(MSG_REVIEW_UNAVAILABLE) + _queue_home()), status)

        def read_context() -> ClinicalReviewContextResponse:
            return clinical_context_service(request, repository).read(review_case_id)

        outcome = generate_ai_assistance(
            case=detail.case,
            context_reader=read_context,
            knowledge=_knowledge(request),
            provider=_assistance_provider(request, settings),
            correlation_id=request.headers.get("x-correlation-id") or "",
        )
        if outcome.context is None and outcome.result.reason in {"case_not_open", "invalid_case_context"}:
            status = 409 if outcome.result.reason == "case_not_open" else 422
            message = (
                "AI assistance is available only for an open review case."
                if outcome.result.reason == "case_not_open"
                else "AI assistance is unavailable for this case."
            )
            return _html(_page("Review case", _error(message) + _queue_home()), status)
        status = 303
        response = _redirect(review_case_id)
        response.set_cookie(
            _HANDOFF_COOKIE,
            _ASSISTANCE_HANDOFF.put(review_case_id, outcome.result),
            max_age=_HANDOFF_TTL_SECONDS,
            httponly=True,
            samesite="strict",
            path=_handoff_path(review_case_id),
        )
        return response
    finally:
        _log(request, "/review-cases/{reviewCaseId}/ai-assistance", status, started, review_case_id)


def submit_controlled_action(
    request: Request,
    settings: Settings,
    review_case_id: str,
    raw_body: bytes,
    content_type: str | None,
) -> Response:
    started = time.perf_counter()
    status = 400
    try:
        session = require_human_session(request, settings)
        if isinstance(session, Response):
            status = session.status_code
            return session
        try:
            review_case_id = validate_review_case_id(review_case_id)
        except ValueError:
            status = 422
            return _html(_page("Review case", _error(MSG_INVALID_LINK) + _queue_home()), status)
        if not _same_origin(request):
            return _html(_page("Review case", _error(MSG_ACTION_ORIGIN_INVALID) + _queue_home()), status)
        fields = _controlled_action_form_fields(raw_body, content_type)
        if fields is None:
            return _html(_page("Review case", _error(MSG_ACTION_INVALID) + _queue_home()), status)
        expiry = _expiry(fields.get("actionExpiry"))
        token = fields.get("actionToken", "")
        if expiry is None:
            return _html(_page("Review case", _error(MSG_ACTION_INVALID) + _queue_home()), status)
        if not settings.human_review_form_signing_secret:
            return _html(_page("Review case", _error(MSG_NOT_CONFIGURED) + _queue_home()), status)
        if not controlled_action_token_is_valid(
            secret=settings.human_review_form_signing_secret,
            review_case_id=review_case_id,
            expiry=expiry,
            token=token,
            session_id=session.session_id,
        ):
            return _html(_page("Review case", _error(MSG_ACTION_TOKEN_INVALID) + _queue_home()), status)
        repository = _repository(request)
        if repository is None:
            status = 503
            return _html(_page("Review case", _error(MSG_REVIEW_UNAVAILABLE) + _queue_home()), status)
        try:
            attribution = _snapshot_from_session(session)
        except ValueError:
            status = 503
            return _html(_page("Review case", _error(MSG_REVIEW_UNAVAILABLE) + _queue_home()), status)
        try:
            FollowUpCoordinationActionService(repository).ensure_follow_up_coordination_request(
                review_case_id,
                attribution=attribution,
            )
        except ReviewCaseNotFound:
            status = 404
            return _html(_page("Review case", _error(MSG_NOT_FOUND) + _queue_home()), status)
        except CoordinationActionDenied:
            status = 409
            return _html(_page("Review case", _error(MSG_ACTION_DENIED) + _queue_home()), status)
        except ReviewPersistenceUnavailable:
            status = 503
            return _html(_page("Review case", _error(MSG_REVIEW_UNAVAILABLE) + _queue_home()), status)
        status = 303
        return _redirect(review_case_id)
    finally:
        _log(request, "/review-cases/{reviewCaseId}/controlled-action", status, started, review_case_id)


def render_observation_value(content: object) -> str:
    """Deterministic HTML for one bounded observation value. Input models only."""
    if isinstance(content, NotProjectedContent) or not hasattr(content, "kind"):
        return _p(MSG_VALUE_HIDDEN)
    if isinstance(content, QuantityContent):
        return _quantity_html(content)
    if isinstance(content, CodedContent):
        return _coded_html(content)
    if isinstance(content, StringContent):
        return _p(content.value)
    if isinstance(content, BooleanContent):
        return _p("true" if content.value else "false")
    if isinstance(content, IntegerContent):
        return _p(str(content.value))
    if isinstance(content, RangeContent):
        return _range_html(content)
    if isinstance(content, ComponentsContent):
        parts = ["<ul>"]
        for component in content.components:
            parts.append("<li>" + _code_html(component.code) + render_observation_value(component.value) + "</li>")
        parts.append("</ul>")
        return "".join(parts)
    return _p(MSG_VALUE_HIDDEN)


def _sign(secret: str, review_case_id: str, expected_version: int, expiry: int, session_id: str) -> str:
    message = f"{review_case_id}|{expected_version}|{expiry}|{session_id}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def _sign_assistance(secret: str, review_case_id: str, expiry: int, session_id: str) -> str:
    message = f"ai-assistance|{review_case_id}|{expiry}|{session_id}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def _sign_controlled_action(secret: str, review_case_id: str, expiry: int, session_id: str) -> str:
    action_type = CoordinationActionType.CREATE_FOLLOW_UP_COORDINATION_REQUEST.value
    message = f"controlled-action|{review_case_id}|{action_type}|{expiry}|{session_id}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def _now() -> int:
    return int(time.time())


def _repository(request: Request):
    return getattr(request.app.state, "followup_review_repository", None)


def _knowledge(request: Request):
    knowledge = getattr(request.app.state, "institutional_knowledge", None)
    if knowledge is None:
        return UnavailableInstitutionalKnowledge()
    return knowledge


def _assistance_provider(request: Request, settings: Settings):
    return resolve_assistance_provider(
        getattr(request.app.state, "ai_assistance_provider", None),
        settings,
    )


def _load_human_attributions(
    request: Request, review_case_id: str
) -> tuple[tuple[StoredDevelopmentAttribution, ...], int | None]:
    repository = _repository(request)
    if repository is None:
        return (), 503
    try:
        return repository.list_human_attributions(review_case_id), None
    except ReviewPersistenceUnavailable:
        return (), 503


def _snapshot_from_session(session: object) -> DevelopmentPrincipalSnapshot:
    return DevelopmentPrincipalSnapshot(
        getattr(session, "principal_id"),
        getattr(session, "authenticator_id"),
        getattr(session, "session_id"),
    )


def _load_coordination_request(
    request: Request, review_case_id: str
) -> tuple[FollowUpCoordinationRequest | None, int | None]:
    repository = _repository(request)
    if repository is None:
        return None, 503
    try:
        return repository.get_follow_up_coordination_request(review_case_id), None
    except ReviewPersistenceUnavailable:
        return None, 503


def _load_detail(request: Request, review_case_id: str) -> tuple[ReviewCaseDetail | None, int | None]:
    repository = _repository(request)
    if repository is None:
        return None, 503
    try:
        return FollowUpReviewCaseService(repository).detail(review_case_id), None
    except ReviewCaseNotFound:
        return None, 404
    except ReviewPersistenceUnavailable:
        return None, 503


def _load_context(
    request: Request,
    case: FollowUpReviewCase,
) -> tuple[ClinicalReviewContextResponse | None, str]:
    if case.status is not ReviewCaseStatus.OPEN:
        return None, MSG_CONTEXT_CLOSED
    repository = _repository(request)
    if repository is None:
        return None, MSG_CONTEXT_UNAVAILABLE
    try:
        return clinical_context_service(request, repository).read(case.id), ""
    except ClinicalContextClosed:
        return None, MSG_CONTEXT_CLOSED
    except (ClinicalContextUnavailable, ReviewPersistenceUnavailable):
        return None, MSG_CONTEXT_UNAVAILABLE


def _same_origin(request: Request) -> bool:
    origin = request.headers.get("origin")
    if origin is None or origin == "":
        return False
    return origin == f"{request.url.scheme}://{request.url.netloc}"


def _form_fields(raw_body: bytes, content_type: str | None) -> dict[str, str] | None:
    return _exact_fields(
        raw_body,
        content_type,
        {"outcome", "expectedVersion", "formToken", "formExpiry"},
    )


def _assistance_form_fields(raw_body: bytes, content_type: str | None) -> dict[str, str] | None:
    return _exact_fields(raw_body, content_type, {"assistanceExpiry", "assistanceToken"})


def _controlled_action_form_fields(raw_body: bytes, content_type: str | None) -> dict[str, str] | None:
    return _exact_fields(raw_body, content_type, {"actionExpiry", "actionToken"})


def _exact_fields(
    raw_body: bytes,
    content_type: str | None,
    allowed: set[str],
) -> dict[str, str] | None:
    if content_type is None or not content_type.startswith("application/x-www-form-urlencoded"):
        return None
    try:
        text = raw_body.decode("utf-8")
    except UnicodeDecodeError:
        return None
    try:
        pairs = parse_qsl(text, keep_blank_values=True, strict_parsing=False, max_num_fields=8)
    except ValueError:
        return None
    fields: dict[str, str] = {}
    for key, value in pairs:
        if key not in allowed or key in fields:
            return None
        fields[key] = value
    if set(fields) != allowed:
        return None
    return fields


def _outcome(value: str | None) -> ReviewOutcome | None:
    try:
        return ReviewOutcome(value)
    except ValueError:
        return None


def _version(value: str | None) -> int | None:
    if value is None or not value.isdigit():
        return None
    parsed = int(value)
    if parsed < 1:
        return None
    return parsed


def _expiry(value: str | None) -> int | None:
    if value is None or not value.isdigit():
        return None
    return int(value)


def _readable_utc(value: str) -> str:
    """Readable UTC for a review timestamp. Any other string stays unchanged."""
    match = _REVIEW_TIMESTAMP.fullmatch(value)
    if match is None:
        return value
    year, month, day, hour, minute, second = (int(part) for part in match.groups())
    if not (1 <= month <= 12 and 1 <= day <= 31 and hour <= 23 and minute <= 59 and second <= 59):
        return value
    return f"{day} de {_MONTHS[month - 1]} de {year}, {hour:02d}:{minute:02d}:{second:02d} UTC"


def _status_label(value: str) -> str:
    if value == ReviewCaseStatus.OPEN.value:
        return "Abierto"
    if value == ReviewCaseStatus.CLOSED.value:
        return "Cerrado"
    return value


def _queue_body(items: tuple[FollowUpReviewCase, ...], next_position: tuple[str, str] | None) -> str:
    parts = [
        _demo_banner(),
        "<p>Casos de revisión abiertos, del más antiguo al más reciente.</p>",
    ]
    if not items:
        parts.append(_p(MSG_EMPTY))
    else:
        rows = []
        for case in items:
            href = "/review-cases/" + quote(case.id, safe="")
            label = _PROTOCOL_LABELS.get(case.protocol_id)
            protocol_cell = (
                f"{esc(label)}<br>{esc(case.protocol_id)}"
                if label
                else esc(case.protocol_id)
            )
            created = _readable_utc(case.created_at)
            created_cell = (
                f"{esc(created)}<br>{esc(case.created_at)}"
                if created != case.created_at
                else esc(case.created_at)
            )
            rows.append(
                "<tr>"
                f"<td><a href=\"{esc(href)}\">{esc(case.case_id)}</a></td>"
                f"<td>{protocol_cell}</td>"
                f"<td>{created_cell}</td>"
                f"<td>{esc(_status_label(case.status.value))}<br>{esc(case.status.value)}</td>"
                "</tr>"
            )
        parts.append(
            "<table>"
            "<caption>Casos abiertos</caption>"
            "<thead><tr>"
            "<th>Caso</th><th>Motivo de revisión</th><th>Creado</th><th>Estado</th>"
            "</tr></thead><tbody>"
            + "".join(rows)
            + "</tbody></table>"
        )
    if next_position is not None:
        cursor = encode_cursor(next_position, status=ReviewCaseStatus.OPEN, case_id=None)
        parts.append(f'<p><a href="/review-cases?cursor={quote(cursor, safe="")}">Casos más antiguos</a></p>')
    parts.append('<p><a href="/review-cases">Actualizar la cola</a></p>')
    return "".join(parts)


def _case_body(
    detail: ReviewCaseDetail,
    context: ClinicalReviewContextResponse | None,
    context_message: str,
    settings: Settings,
    notice: str,
    assistance: AssistanceResult | None,
    coordination: FollowUpCoordinationRequest | None,
    attributions: tuple[StoredDevelopmentAttribution, ...],
    session_id: str,
) -> str:
    case = detail.case
    parts = [_demo_banner(), _queue_home()]
    if notice:
        parts.append(_error(notice))
    parts.append(_operational_section(case))
    parts.append(_provenance_section(case))
    parts.append(_context_section(context, context_message))
    parts.append(_history_section(detail.events))
    parts.append(_attribution_section(case, attributions))
    parts.append(_assistance_section(case, settings, assistance, session_id))
    parts.append(_outcome_section(case, settings, coordination, session_id))
    parts.append(_controlled_action_section(case, settings, coordination, attributions, session_id))
    parts.append(_technical_details(detail, context, coordination))
    return "".join(parts)


def _controlled_action_eligible(case: FollowUpReviewCase) -> bool:
    return (
        case.status is ReviewCaseStatus.CLOSED
        and case.outcome is ReviewOutcome.FOLLOW_UP_COORDINATION_PLANNED
        and case.protocol_id in PERSISTABLE_PROTOCOL_IDS
    )


def _attribution_for(
    attributions: tuple[StoredDevelopmentAttribution, ...], operation: str
) -> StoredDevelopmentAttribution | None:
    for item in attributions:
        if item.operation == operation:
            return item
    return None


def _attribution_section(
    case: FollowUpReviewCase,
    attributions: tuple[StoredDevelopmentAttribution, ...],
) -> str:
    closure = _attribution_for(attributions, REVIEW_CASE_CLOSED)
    if case.status is not ReviewCaseStatus.CLOSED:
        closure_line = "Cierre del caso: aún no está cerrado."
    elif closure is None:
        closure_line = "Cierre del caso: no se registró atribución de desarrollo."
    else:
        closure_line = (
            f"Cierre del caso: principal sintético de desarrollo {closure.principal_id}. "
            f"Registrado {_readable_utc(closure.occurred_at)}."
        )
    return (
        "<section><h2>Atribución de desarrollo</h2>"
        "<p>Los identificadores mostrados son principales sintéticos de desarrollo, "
        "no una identidad clínica verificada.</p>"
        f"<p>{esc(closure_line)}</p>"
        "</section>"
    )


def _controlled_action_section(
    case: FollowUpReviewCase,
    settings: Settings,
    coordination: FollowUpCoordinationRequest | None,
    attributions: tuple[StoredDevelopmentAttribution, ...],
    session_id: str,
) -> str:
    if coordination is not None:
        recorded = _attribution_for(attributions, COORDINATION_REQUEST_CREATED)
        if recorded is None:
            attribution_line = "No se registró atribución de desarrollo para esta operación."
        else:
            attribution_line = (
                f"Principal sintético de desarrollo {recorded.principal_id}. "
                f"Registrado {_readable_utc(recorded.occurred_at)}."
            )
        return (
            "<section><h2>Solicitud de coordinación interna</h2>"
            f"<p>{esc(_SENTENCE_RECORDED)}</p>"
            f"<p>{esc(_SENTENCE_NO_EXTERNAL)}</p>"
            f"<p>{esc(attribution_line)}</p>"
            "</section>"
        )
    if not _controlled_action_eligible(case):
        return ""
    issued = issue_controlled_action_token(
        secret=settings.human_review_form_signing_secret,
        review_case_id=case.id,
        session_id=session_id,
    )
    if issued is None:
        return "<section><h2>Solicitud de coordinación interna</h2>" + _error(MSG_NOT_CONFIGURED) + "</section>"
    token, expiry = issued
    action = "/review-cases/" + quote(case.id, safe="") + "/controlled-action"
    return (
        "<section><h2>Solicitud de coordinación interna</h2>"
        "<p>Esta acción es un segundo paso. Cerrar el caso no crea la solicitud.</p>"
        f'<form method="post" action="{esc(action)}">'
        f'<input type="hidden" name="actionExpiry" value="{esc(str(expiry))}">'
        f'<input type="hidden" name="actionToken" value="{esc(token)}">'
        '<button type="submit">Registrar solicitud de coordinación interna</button>'
        "</form></section>"
    )


def _assistance_section(
    case: FollowUpReviewCase,
    settings: Settings,
    assistance: AssistanceResult | None,
    session_id: str,
) -> str:
    open_case = case.status is ReviewCaseStatus.OPEN
    token = (
        issue_assistance_token(
            secret=settings.human_review_form_signing_secret,
            review_case_id=case.id,
            session_id=session_id,
        )
        if open_case
        else None
    )
    return render_assistance_section(
        open_case=open_case,
        review_case_id=case.id,
        token=token,
        result=assistance,
    )


def _operational_section(case: FollowUpReviewCase) -> str:
    closed = _readable_utc(case.closed_at) if case.closed_at else "Ninguno"
    return (
        "<section><h2>Resumen del caso</h2>"
        "<dl>"
        f"<dt>Caso</dt><dd>{esc(case.case_id)}</dd>"
        f"<dt>Estado</dt><dd>{esc(_status_label(case.status.value))}</dd>"
        f"<dt>Creado</dt><dd>{esc(_readable_utc(case.created_at))}</dd>"
        f"<dt>Cerrado</dt><dd>{esc(closed)}</dd>"
        "</dl></section>"
    )


def _provenance_section(case: FollowUpReviewCase) -> str:
    label = _PROTOCOL_LABELS.get(case.protocol_id, case.protocol_id)
    reasons = []
    for reason in case.reason_codes:
        reasons.append(f"<li>{esc(_PAGE_REASONS.get(reason, reason))}</li>")
    matched = f"<p>{esc(_RULE_MATCHED)}</p>" if case.protocol_evaluation_status == "matched" else ""
    return (
        "<section><h2>Por qué está en revisión</h2>"
        f"<p>{esc(label)}</p>"
        "<ul>"
        + "".join(reasons)
        + "</ul>"
        + matched
        + "</section>"
    )


def _context_section(context: ClinicalReviewContextResponse | None, message: str) -> str:
    parts = [
        "<section><h2>Contexto clínico actual</h2>",
        f"<p>{esc(MSG_CONTEXT_SCOPE)}</p>",
        f"<p>{esc(MSG_PATIENT_HIDDEN)}</p>",
    ]
    if message:
        parts.append(_p(message))
    if context is not None:
        parts.append(f"<p>Leído {esc(_readable_utc(context.retrieval.retrieved_at))}</p>")
        if context.current_context.encounter is not None:
            parts.append(_encounter_html(context))
        if context.current_context.observation is not None:
            parts.append(_observation_html(context))
        if context.current_context.trigger_appointment is not None:
            parts.append(_trigger_appointment_html(context))
        parts.append(_appointments_html(context))
    parts.append("</section>")
    return "".join(parts)


def _encounter_html(context: ClinicalReviewContextResponse) -> str:
    encounter = context.current_context.encounter
    if encounter.availability == "not_found":
        body = _p(MSG_ENCOUNTER_MISSING)
    else:
        period = ""
        if encounter.period is not None:
            start = encounter.period.start or "None"
            end = encounter.period.end or "None"
            period = f"<dt>Period start</dt><dd>{esc(start)}</dd><dt>Period end</dt><dd>{esc(end)}</dd>"
        body = f"<dl><dt>Status</dt><dd>{esc(encounter.status)}</dd>{period}</dl>"
    return "<h3>Encounter</h3>" + body


def _observation_html(context: ClinicalReviewContextResponse) -> str:
    observation = context.current_context.observation
    if observation.availability == "not_found":
        body = _p(MSG_OBSERVATION_MISSING)
    else:
        issued = observation.issued or "None"
        body = (
            "<dl>"
            f"<dt>Status</dt><dd>{esc(observation.status)}</dd>"
            f"<dt>Issued</dt><dd>{esc(issued)}</dd>"
            "</dl>"
            "<h4>Code</h4>"
            + _code_html(observation.code)
            + "<h4>Value</h4>"
            + render_observation_value(observation.content)
        )
    return "<h3>Observation</h3>" + body


def _trigger_appointment_html(context: ClinicalReviewContextResponse) -> str:
    trigger = context.current_context.trigger_appointment
    if trigger is None:
        return ""
    if trigger.availability == "not_found":
        body = _p(MSG_APPOINTMENT_MISSING)
    else:
        start = trigger.start or "None"
        body = (
            "<dl>"
            f"<dt>Status</dt><dd>{esc(trigger.status)}</dd>"
            f"<dt>Start</dt><dd>{esc(start)}</dd>"
            "</dl>"
        )
    return (
        f"<h3>{esc(_ORIGIN_APPOINTMENT)}</h3>"
        + body
        + f"<p>{esc(trigger.reference)}</p>"
    )


def _appointments_html(context: ClinicalReviewContextResponse) -> str:
    appointments = context.current_context.appointments
    trigger = context.current_context.trigger_appointment
    trigger_reference = trigger.reference if trigger is not None else None
    labels = []
    for classification in appointments.classifications:
        labels.append(f"<li>{esc(_APPOINTMENT_LABELS.get(classification, classification))}</li>")
    items = []
    omitted_origin = False
    for item in appointments.items:
        if trigger_reference is not None and item.reference == trigger_reference:
            omitted_origin = True
            continue
        start = item.start or "None"
        items.append(
            "<li>"
            f"<p>{esc(_APPOINTMENT_LABELS.get(item.classification, item.classification))}</p>"
            "<dl>"
            f"<dt>Status</dt><dd>{esc(item.status)}</dd>"
            f"<dt>Start</dt><dd>{esc(start)}</dd>"
            "</dl>"
            "</li>"
        )
    item_html = "<ul>" + "".join(items) + "</ul>" if items else ""
    pointer = _p(_ORIGIN_POINTER) if omitted_origin else ""
    return (
        "<h3>Appointments</h3><ul>"
        + "".join(labels)
        + "</ul>"
        + pointer
        + item_html
    )


def _code_html(code: ObservationCode) -> str:
    if code.status != "available":
        return _p(MSG_CODE_HIDDEN)
    parts = []
    if code.text:
        parts.append(_p(code.text))
    if code.coding:
        entries = []
        for entry in code.coding:
            bits = []
            if entry.display:
                bits.append(entry.display)
            if entry.code:
                bits.append(entry.code)
            if entry.system:
                bits.append(entry.system)
            entries.append("<li>" + esc(" | ".join(bits)) + "</li>")
        parts.append("<ul>" + "".join(entries) + "</ul>")
    if not parts:
        return _p(MSG_CODE_HIDDEN)
    return "".join(parts)


def _quantity_html(content: QuantityContent | QuantityFields) -> str:
    comparator = f"{content.comparator} " if content.comparator else ""
    unit = f" {content.unit}" if content.unit else ""
    lines = [_p(f"{comparator}{content.value}{unit}")]
    if content.system or content.code:
        lines.append(
            "<p>Technical quantity code: "
            + esc(" | ".join(bit for bit in (content.system, content.code) if bit))
            + "</p>"
        )
    return "".join(lines)


def _coded_html(content: CodedContent) -> str:
    return _code_html(
        ObservationCode(status="available", coding=content.coding, text=content.text)
    )


def _range_html(content: RangeContent) -> str:
    parts = ["<ul>"]
    if content.low is not None:
        parts.append("<li>Lower bound " + _quantity_html(content.low) + "</li>")
    if content.high is not None:
        parts.append("<li>Upper bound " + _quantity_html(content.high) + "</li>")
    parts.append("</ul>")
    return "".join(parts)


def _history_section(events: tuple[FollowUpReviewCaseEvent, ...]) -> str:
    rows = []
    for event in events:
        outcome = _HISTORY_OUTCOMES[event.outcome] if event.outcome is not None else "Ninguno"
        source = _status_label(event.from_status.value) if event.from_status is not None else "Ninguno"
        label = "Creado" if event.event_type.value == "created" else "Cerrado"
        rows.append(
            "<tr>"
            f"<td>{esc(label)}</td>"
            f"<td>{esc(source)}</td>"
            f"<td>{esc(_status_label(event.to_status.value))}</td>"
            f"<td>{esc(outcome)}</td>"
            f"<td>{esc(_readable_utc(event.occurred_at))}</td>"
            "</tr>"
        )
    return (
        "<section><h2>Historial operativo</h2><table>"
        "<thead><tr><th>Evento</th><th>Desde</th><th>Hasta</th><th>Resultado</th><th>Cuándo</th></tr></thead>"
        "<tbody>"
        + "".join(rows)
        + "</tbody></table></section>"
    )


def _outcome_section(
    case: FollowUpReviewCase,
    settings: Settings,
    coordination: FollowUpCoordinationRequest | None,
    session_id: str,
) -> str:
    if case.status is not ReviewCaseStatus.OPEN:
        if coordination is not None:
            return ""
        if case.outcome is ReviewOutcome.FOLLOW_UP_COORDINATION_PLANNED:
            sentence = _SENTENCE_PENDING
        elif case.outcome is ReviewOutcome.REVIEW_COMPLETED_NO_OPERATIONAL_ACTION:
            sentence = _SENTENCE_NO_ACTION
        else:
            return ""
        return (
            "<section><h2>Resultado operativo</h2>"
            f"<p>{esc(sentence)}</p>"
            "</section>"
        )
    issued = issue_form_token(
        secret=settings.human_review_form_signing_secret,
        review_case_id=case.id,
        expected_version=case.version,
        session_id=session_id,
    )
    if issued is None:
        return "<section><h2>Resultado operativo</h2>" + _error(MSG_NOT_CONFIGURED) + "</section>"
    token, expiry = issued
    action = "/review-cases/" + quote(case.id, safe="") + "/close"
    options = [
        (
            f'<label><input type="radio" name="outcome" value="{esc(ReviewOutcome.FOLLOW_UP_COORDINATION_PLANNED.value)}" required> '
            f"{esc(_SENTENCE_PENDING)}</label>"
        ),
        (
            f'<label><input type="radio" name="outcome" value="{esc(ReviewOutcome.REVIEW_COMPLETED_NO_OPERATIONAL_ACTION.value)}" required> '
            f"{esc(_SENTENCE_NO_ACTION)}</label>"
        ),
    ]
    return (
        "<section><h2>Resultado operativo</h2>"
        f"<p>{esc(MSG_CLOSE_SCOPE)}</p>"
        f'<form method="post" action="{esc(action)}">'
        '<fieldset><legend>Resultado operativo</legend>'
        + "".join(options)
        + "</fieldset>"
        f'<input type="hidden" name="expectedVersion" value="{esc(str(case.version))}">'
        f'<input type="hidden" name="formExpiry" value="{esc(str(expiry))}">'
        f'<input type="hidden" name="formToken" value="{esc(token)}">'
        '<button type="submit">Cerrar la revisión</button>'
        "</form></section>"
    )


def _technical_details(
    detail: ReviewCaseDetail,
    context: ClinicalReviewContextResponse | None,
    coordination: FollowUpCoordinationRequest | None,
) -> str:
    """Original identifiers and timestamps. The group is closed and does not fetch FHIR."""
    case = detail.case
    outcome = case.outcome.value if case.outcome is not None else ""
    parts = [
        "<details>",
        "<summary>Detalles técnicos</summary>",
        "<dl>",
        f"<dt>Protocolo</dt><dd>{esc(case.protocol_id)}</dd>",
        f"<dt>Evaluación</dt><dd>{esc(case.protocol_evaluation_status)}</dd>",
        f"<dt>Versión</dt><dd>{esc(str(case.version))}</dd>",
        f"<dt>Estado</dt><dd>{esc(case.status.value)}</dd>",
        f"<dt>Resultado</dt><dd>{esc(outcome)}</dd>",
        f"<dt>Creado</dt><dd>{esc(case.created_at)}</dd>",
        f"<dt>Actualizado</dt><dd>{esc(case.updated_at)}</dd>",
        f"<dt>Cerrado</dt><dd>{esc(case.closed_at or '')}</dd>",
        "</dl>",
        "<h3>Códigos de motivo</h3><ul>",
    ]
    for reason in case.reason_codes:
        parts.append(f"<li>{esc(reason)}</li>")
    parts.append("</ul><h3>Recursos coincidentes</h3><ul>")
    for resource in case.matched_resources:
        parts.append(f"<li>{esc(resource)}</li>")
    parts.append("</ul><h3>Eventos</h3><ul>")
    for event in detail.events:
        parts.append(f"<li>{esc(event.event_type.value)} {esc(event.occurred_at)}</li>")
    parts.append("</ul>")
    if context is not None:
        parts.append(f"<p>{esc(context.retrieval.retrieved_at)}</p>")
        parts.append("<h3>Referencias FHIR</h3><ul>")
        for reference in _context_references(context):
            parts.append(f"<li>{esc(reference)}</li>")
        parts.append("</ul><h3>Códigos</h3><ul>")
        for code in _context_codes(context):
            parts.append(f"<li>{esc(code)}</li>")
        parts.append("</ul>")
    if coordination is not None:
        parts.append(
            "<dl>"
            f"<dt>Solicitud</dt><dd>{esc(coordination.id)}</dd>"
            f"<dt>Estado de la solicitud</dt><dd>{esc(coordination.status.value)}</dd>"
            f"<dt>Creada</dt><dd>{esc(coordination.created_at)}</dd>"
            "</dl>"
        )
    parts.append("</details>")
    return "".join(parts)


def _context_references(context: ClinicalReviewContextResponse) -> list[str]:
    current = context.current_context
    references: list[str] = []
    if current.encounter is not None:
        references.append(current.encounter.reference)
    if current.observation is not None:
        references.append(current.observation.reference)
        if current.observation.availability == "available":
            references.append(current.observation.encounter_reference)
    if current.trigger_appointment is not None:
        references.append(current.trigger_appointment.reference)
    for item in current.appointments.items:
        references.append(item.reference)
    return references


def _context_codes(context: ClinicalReviewContextResponse) -> list[str]:
    current = context.current_context
    codes = [str(item) for item in current.appointments.classifications]
    for item in current.appointments.items:
        codes.append(item.status)
        codes.append(str(item.classification))
    observation = current.observation
    if observation is not None and observation.availability == "available" and observation.code.coding:
        for entry in observation.code.coding:
            if entry.system:
                codes.append(entry.system)
            if entry.code:
                codes.append(entry.code)
    return codes


def _demo_banner() -> str:
    return f'<p class="demo">{esc(MSG_DEMO)}</p>'


def _queue_home() -> str:
    return '<p><a href="/review-cases">Cola de revisión</a></p>'


def _error(message: str) -> str:
    return f'<p class="notice">{esc(message)}</p>'


def _p(message: str) -> str:
    return f"<p>{esc(message)}</p>"


def _page(title: str, body: str) -> str:
    return (
        "<!DOCTYPE html>\n<html lang=\"es\">\n<head>\n"
        '<meta charset="utf-8">\n'
        f"<title>{esc(title)}</title>\n"
        '<link rel="stylesheet" href="/review-static/review.css">\n'
        "</head>\n<body>\n"
        f"<h1>{esc(title)}</h1>\n"
        f"{body}\n"
        "</body>\n</html>\n"
    )


def _html(content: str, status_code: int = 200) -> HTMLResponse:
    return HTMLResponse(content=content, status_code=status_code, headers={"Cache-Control": "no-store"})


def _handoff_path(review_case_id: str) -> str:
    return "/review-cases/" + quote(review_case_id, safe="")


def _redirect(review_case_id: str, *, notice: bool = False) -> RedirectResponse:
    url = "/review-cases/" + quote(review_case_id, safe="")
    if notice:
        url += "?notice=changed"
    return RedirectResponse(url=url, status_code=303, headers={"Cache-Control": "no-store"})


def esc(value: str) -> str:
    return escape(value, quote=True)


def _log(
    request: Request,
    route: str,
    status: int,
    started: float,
    review_case_id: str | None = None,
) -> None:
    correlation = request.headers.get("x-correlation-id") or ""
    if _CORRELATION.fullmatch(correlation) is None:
        correlation = str(uuid.uuid4())
    case_label = review_case_id if review_case_id and _safe_case_id(review_case_id) else "-"
    duration_ms = int((time.perf_counter() - started) * 1000)
    log.info(
        "human_review route=%s status=%s durationMs=%s correlationId=%s reviewCaseId=%s",
        route,
        status,
        duration_ms,
        correlation,
        case_label,
    )


def _safe_case_id(value: str) -> bool:
    try:
        validate_review_case_id(value)
    except ValueError:
        return False
    return True
