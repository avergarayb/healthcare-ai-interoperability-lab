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
import time
import uuid
from html import escape
from urllib.parse import parse_qsl, quote

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

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
from app.clinical_review_context_http import clinical_context_service
from app.config import Settings
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

_OUTCOME_LABELS = {
    ReviewOutcome.FOLLOW_UP_COORDINATION_PLANNED: "Follow-up coordination planned",
    ReviewOutcome.REVIEW_COMPLETED_NO_OPERATIONAL_ACTION: "Review completed, no operational action recorded",
}
_REASON_LABELS = {
    "post_consultation_result_requires_review": (
        "A post-consultation result was selected for operational review."
    ),
}
_APPOINTMENT_LABELS = {
    "NONE": "No appointments were returned.",
    "UPCOMING_CONFIRMED": "Upcoming, confirmed",
    "UPCOMING_UNCONFIRMED": "Upcoming, not confirmed",
    "CANCELLED": "Cancelled",
    "PAST": "Past",
    "OTHER": "Other appointment status",
}

MSG_EMPTY = "There are no open review cases."
MSG_CURSOR = "This page link is no longer valid."
MSG_REVIEW_UNAVAILABLE = "Review service is unavailable."
MSG_NOT_FOUND = "This review case was not found."
MSG_INVALID_LINK = "This review link is not valid."
MSG_CONTEXT_UNAVAILABLE = "Current clinical context is temporarily unavailable."
MSG_CONTEXT_CLOSED = "Current clinical context is not available for a closed case."
MSG_ENCOUNTER_MISSING = "The recorded encounter was not found."
MSG_OBSERVATION_MISSING = "The recorded observation was not found."
MSG_VALUE_HIDDEN = "Result value is not available in this view."
MSG_CODE_HIDDEN = "Result code is not available in this view."
MSG_CLOSE_INVALID = "The close request was not valid."
MSG_FORM_INVALID = "This close form is no longer valid."
MSG_ORIGIN_INVALID = "This close form was not sent from this demo."
MSG_NOT_CONFIGURED = "This demo is not configured."
MSG_CHANGED = "This case changed. Review the current version before closing."
MSG_CONTEXT_SCOPE = "Current clinical context is a current read. It does not re-run the original protocol."
MSG_CLOSE_SCOPE = (
    "This records an operational review outcome. It is not a diagnosis or a treatment decision."
)
MSG_DEMO = (
    "Controlled synthetic demo. This page is not a user login. "
    "Anyone who can reach this demo can view synthetic review cases. "
    "caseId is an operational identifier, not a patient identity."
)
MSG_PATIENT_HIDDEN = "Patient identity is not shown in this view."


def issue_form_token(
    *,
    secret: str,
    review_case_id: str,
    expected_version: int,
    now: int | None = None,
) -> tuple[str, int] | None:
    """Sign the close parameters for a short window. Returns None without a server secret."""
    if not secret:
        return None
    issued_at = _now() if now is None else now
    expiry = issued_at + FORM_TTL_SECONDS
    return _sign(secret, review_case_id, expected_version, expiry), expiry


def form_token_is_valid(
    *,
    secret: str,
    review_case_id: str,
    expected_version: int,
    expiry: int,
    token: str,
    now: int | None = None,
) -> bool:
    """Check that this presentation layer issued the submitted case, version and expiry."""
    if not secret or not token:
        return False
    current = _now() if now is None else now
    if expiry > current + FORM_TTL_SECONDS or current >= expiry:
        return False
    expected = _sign(secret, review_case_id, expected_version, expiry)
    try:
        return hmac.compare_digest(expected, token)
    except TypeError:
        return False


def render_review_queue(request: Request, settings: Settings) -> Response:
    started = time.perf_counter()
    status = 200
    try:
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
        return _html(_page("Review queue", _queue_body(page.items, page.next_position)))
    finally:
        _log(request, "/review-cases", status, started)


def render_review_case(request: Request, settings: Settings, review_case_id: str) -> Response:
    started = time.perf_counter()
    status = 200
    try:
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
        notice = MSG_CHANGED if request.query_params.get("notice") == "changed" else ""
        context, context_message = _load_context(request, detail.case)
        body = _case_body(detail, context, context_message, settings, notice)
        return _html(_page("Review case", body))
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
        ):
            return _html(_page("Review case", _error(MSG_FORM_INVALID) + _queue_home()), status)
        repository = _repository(request)
        if repository is None:
            status = 503
            return _html(_page("Review case", _error(MSG_REVIEW_UNAVAILABLE) + _queue_home()), status)
        service = FollowUpReviewCaseService(repository)
        try:
            service.close(review_case_id, expected_version=version, outcome=outcome)
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


def _sign(secret: str, review_case_id: str, expected_version: int, expiry: int) -> str:
    message = f"{review_case_id}|{expected_version}|{expiry}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def _now() -> int:
    return int(time.time())


def _repository(request: Request):
    return getattr(request.app.state, "followup_review_repository", None)


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
    allowed = {"outcome", "expectedVersion", "formToken", "formExpiry"}
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


def _queue_body(items: tuple[FollowUpReviewCase, ...], next_position: tuple[str, str] | None) -> str:
    parts = [_demo_banner(), "<p>Open review cases, oldest first.</p>"]
    if not items:
        parts.append(_p(MSG_EMPTY))
    else:
        rows = []
        for case in items:
            href = "/review-cases/" + quote(case.id, safe="")
            rows.append(
                "<tr>"
                f"<td><a href=\"{esc(href)}\">{esc(case.case_id)}</a></td>"
                f"<td>{esc(case.protocol_id)}</td>"
                f"<td>{esc(case.created_at)}</td>"
                f"<td>{esc(case.status.value)}</td>"
                "</tr>"
            )
        parts.append(
            "<table>"
            "<caption>Open operational review cases</caption>"
            "<thead><tr>"
            "<th>Operational case id</th><th>Protocol</th><th>Created</th><th>Status</th>"
            "</tr></thead><tbody>"
            + "".join(rows)
            + "</tbody></table>"
        )
    if next_position is not None:
        cursor = encode_cursor(next_position, status=ReviewCaseStatus.OPEN, case_id=None)
        parts.append(f'<p><a href="/review-cases?cursor={quote(cursor, safe="")}">Older cases</a></p>')
    parts.append('<p><a href="/review-cases">Refresh queue</a></p>')
    return "".join(parts)


def _case_body(
    detail: ReviewCaseDetail,
    context: ClinicalReviewContextResponse | None,
    context_message: str,
    settings: Settings,
    notice: str,
) -> str:
    case = detail.case
    parts = [_demo_banner(), _queue_home()]
    if notice:
        parts.append(_error(notice))
    parts.append(_operational_section(case))
    parts.append(_provenance_section(case))
    parts.append(_context_section(context, context_message))
    parts.append(_history_section(detail.events))
    parts.append(_outcome_section(case, settings))
    return "".join(parts)


def _operational_section(case: FollowUpReviewCase) -> str:
    outcome = _OUTCOME_LABELS[case.outcome] if case.outcome is not None else "None"
    closed = case.closed_at or "None"
    return (
        "<section><h2>Operational case</h2>"
        "<dl>"
        f"<dt>Operational case id</dt><dd>{esc(case.case_id)}</dd>"
        f"<dt>Status</dt><dd>{esc(case.status.value)}</dd>"
        f"<dt>Version</dt><dd>{esc(str(case.version))}</dd>"
        f"<dt>Created</dt><dd>{esc(case.created_at)}</dd>"
        f"<dt>Updated</dt><dd>{esc(case.updated_at)}</dd>"
        f"<dt>Closed</dt><dd>{esc(closed)}</dd>"
        f"<dt>Outcome</dt><dd>{esc(outcome)}</dd>"
        "</dl></section>"
    )


def _provenance_section(case: FollowUpReviewCase) -> str:
    reasons = []
    for reason in case.reason_codes:
        label = _REASON_LABELS.get(reason, reason)
        reasons.append(f"<li>{esc(label)}</li>")
    resources = "".join(f"<li>{esc(resource)}</li>" for resource in case.matched_resources)
    matched = "The original review rule matched." if case.protocol_evaluation_status == "matched" else ""
    return (
        "<section><h2>Why this case was created</h2>"
        "<p>This section is the original trigger recorded when the case was created.</p>"
        "<dl>"
        f"<dt>Protocol</dt><dd>{esc(case.protocol_id)}</dd>"
        f"<dt>Evaluation status</dt><dd>{esc(case.protocol_evaluation_status)}</dd>"
        "</dl>"
        f"<p>{esc(matched)}</p>"
        "<h3>Reason</h3><ul>"
        + "".join(reasons)
        + "</ul>"
        "<h3>Technical provenance</h3><ul>"
        + resources
        + "</ul></section>"
    )


def _context_section(context: ClinicalReviewContextResponse | None, message: str) -> str:
    parts = [
        "<section><h2>Current clinical context</h2>",
        f"<p>{esc(MSG_CONTEXT_SCOPE)}</p>",
        f"<p>{esc(MSG_PATIENT_HIDDEN)}</p>",
    ]
    if message:
        parts.append(_p(message))
    if context is not None:
        parts.append(f"<p>Retrieved {esc(context.retrieval.retrieved_at)}</p>")
        parts.append(_encounter_html(context))
        parts.append(_observation_html(context))
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
    technical = f"<p>Technical reference: {esc(encounter.reference)}</p>"
    return "<h3>Encounter</h3>" + body + technical


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
    technical = f"<p>Technical reference: {esc(observation.reference)}</p>"
    return "<h3>Observation</h3>" + body + technical


def _appointments_html(context: ClinicalReviewContextResponse) -> str:
    appointments = context.current_context.appointments
    labels = []
    for classification in appointments.classifications:
        labels.append(f"<li>{esc(_APPOINTMENT_LABELS.get(classification, classification))}</li>")
    items = []
    for item in appointments.items:
        start = item.start or "None"
        items.append(
            "<li>"
            f"<p>{esc(_APPOINTMENT_LABELS.get(item.classification, item.classification))}</p>"
            "<dl>"
            f"<dt>Status</dt><dd>{esc(item.status)}</dd>"
            f"<dt>Start</dt><dd>{esc(start)}</dd>"
            "</dl>"
            f"<p>Technical reference: {esc(item.reference)}</p>"
            "</li>"
        )
    item_html = "<ul>" + "".join(items) + "</ul>" if items else ""
    return (
        "<h3>Appointments</h3><ul>"
        + "".join(labels)
        + "</ul>"
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
        outcome = _OUTCOME_LABELS[event.outcome] if event.outcome is not None else "None"
        source = event.from_status.value if event.from_status is not None else "None"
        rows.append(
            "<tr>"
            f"<td>{esc(event.event_type.value)}</td>"
            f"<td>{esc(source)}</td>"
            f"<td>{esc(event.to_status.value)}</td>"
            f"<td>{esc(outcome)}</td>"
            f"<td>{esc(event.occurred_at)}</td>"
            "</tr>"
        )
    return (
        "<section><h2>Review history</h2><table>"
        "<thead><tr><th>Event</th><th>From</th><th>To</th><th>Outcome</th><th>When</th></tr></thead>"
        "<tbody>"
        + "".join(rows)
        + "</tbody></table></section>"
    )


def _outcome_section(case: FollowUpReviewCase, settings: Settings) -> str:
    if case.status is not ReviewCaseStatus.OPEN:
        return (
            "<section><h2>Operational outcome</h2>"
            f"<p>This case is closed. {esc(_OUTCOME_LABELS[case.outcome]) if case.outcome else ''}</p>"
            "</section>"
        )
    issued = issue_form_token(
        secret=settings.human_review_form_signing_secret,
        review_case_id=case.id,
        expected_version=case.version,
    )
    if issued is None:
        return "<section><h2>Operational outcome</h2>" + _error(MSG_NOT_CONFIGURED) + "</section>"
    token, expiry = issued
    action = "/review-cases/" + quote(case.id, safe="") + "/close"
    options = []
    for outcome, label in _OUTCOME_LABELS.items():
        options.append(
            f'<label><input type="radio" name="outcome" value="{esc(outcome.value)}" required> '
            f"{esc(label)}</label>"
        )
    return (
        "<section><h2>Operational outcome</h2>"
        f"<p>{esc(MSG_CLOSE_SCOPE)}</p>"
        f'<form method="post" action="{esc(action)}">'
        '<fieldset><legend>Operational outcome</legend>'
        + "".join(options)
        + "</fieldset>"
        f'<input type="hidden" name="expectedVersion" value="{esc(str(case.version))}">'
        f'<input type="hidden" name="formExpiry" value="{esc(str(expiry))}">'
        f'<input type="hidden" name="formToken" value="{esc(token)}">'
        '<button type="submit">Close review</button>'
        "</form></section>"
    )


def _demo_banner() -> str:
    return f'<p class="demo">{esc(MSG_DEMO)}</p>'


def _queue_home() -> str:
    return '<p><a href="/review-cases">Review queue</a></p>'


def _error(message: str) -> str:
    return f'<p class="notice">{esc(message)}</p>'


def _p(message: str) -> str:
    return f"<p>{esc(message)}</p>"


def _page(title: str, body: str) -> str:
    return (
        "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n"
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
