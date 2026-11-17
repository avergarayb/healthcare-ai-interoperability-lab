"""Laboratory pages for one human decision on a lab summary.

The session principal is resolved by the existing development login. A posted
role is ignored because it is not accepted as a field. No model is called.
"""
from datetime import datetime, timezone
from html import escape
from urllib.parse import parse_qsl, quote

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from app.config import Settings
from app.human_development_auth import require_human_session

from .review import ReviewError, Reviewer, decide, list_reviews, read_review


def render_lab_summary_queue(request: Request, settings: Settings) -> Response:
    session = require_human_session(request, settings)
    if isinstance(session, Response):
        return session
    path = _path(settings)
    if path is None:
        return _html(_page("Resumenes de laboratorio", _p("El almacén de revisión no está configurado.")), 503)
    try:
        rows = list_reviews(path)
    except ReviewError:
        return _html(_page("Resumenes de laboratorio", _p("La revisión no está disponible.")), 503)
    pending = [row for row in rows if row["decision"] is None]
    decided = [row for row in rows if row["decision"] is not None]
    body = "<h2>Pendientes</h2>" + _table(pending, empty="No hay resúmenes pendientes.")
    body += "<h2>Historial</h2>" + _table(decided, empty="Todavía no hay decisiones.")
    return _html(_page("Resumenes de laboratorio", body))


def render_lab_summary(request: Request, settings: Settings, review_id: str) -> Response:
    session = require_human_session(request, settings)
    if isinstance(session, Response):
        return session
    path = _path(settings)
    if path is None:
        return _html(_page("Resumen", _p("El almacén de revisión no está configurado.")), 503)
    try:
        case = read_review(path, review_id)
    except ReviewError as error:
        status = 404 if error.reason == "not_found" else 503
        return _html(_page("Resumen", _p("El resumen no está disponible.") + _home()), status)
    return _html(_page("Resumen de laboratorio", _detail(case)))


def submit_lab_summary_decision(
    request: Request, settings: Settings, review_id: str, raw_body: bytes, content_type: str | None,
) -> Response:
    session = require_human_session(request, settings)
    if isinstance(session, Response):
        return session
    path = _path(settings)
    if path is None:
        return _html(_page("Resumen", _p("El almacén de revisión no está configurado.")), 503)
    if not _same_origin(request):
        return _html(_page("Resumen", _p("La decisión no fue aceptada.") + _home()), 403)
    fields = _fields(raw_body, content_type)
    if fields is None:
        return _html(_page("Resumen", _p("La decisión no fue aceptada.") + _home()), 422)
    try:
        reviewer = Reviewer(session.principal_id, session.authenticator_id, session.session_id)
        decide(
            path, review_id, reviewer, fields["decision"], fields["note"],
            datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"))
    except ReviewError as error:
        if error.reason == "already_decided":
            return _html(_page("Resumen", _p("Este resumen ya tiene una decisión.") + _home()), 409)
        if error.reason == "reviewer_denied":
            return _html(_page("Resumen", _p("El revisor no está autorizado.") + _home()), 403)
        if error.reason == "schema_unprepared":
            return _html(_page("Resumen", _p("Falta la preparación explícita del almacén de decisiones.") + _home()), 503)
        status = 404 if error.reason == "not_found" else 422
        return _html(_page("Resumen", _p("La decisión no fue aceptada.") + _home()), status)
    return RedirectResponse("/lab-summaries/" + quote(review_id, safe=""), status_code=303)


def _path(settings):
    value = settings.lab_summary_review_db_path
    if type(value) is not str or value.strip() == "":
        return None
    return value


def _fields(raw_body, content_type):
    if len(raw_body) > 2048 or content_type is None:
        return None
    if not content_type.startswith("application/x-www-form-urlencoded"):
        return None
    try:
        pairs = parse_qsl(raw_body.decode("utf-8"), keep_blank_values=True, max_num_fields=4)
    except (UnicodeDecodeError, ValueError):
        return None
    fields = {}
    for key, value in pairs:
        if key in fields or key not in {"decision", "note"}:
            return None
        fields[key] = value
    if set(fields) != {"decision", "note"}:
        return None
    return fields


def _same_origin(request):
    origin = request.headers.get("origin")
    return origin == f"{request.url.scheme}://{request.url.netloc}"


def _table(rows, empty):
    if not rows:
        return _p(empty)
    items = []
    for row in rows:
        label = row["decision"] or "pending"
        href = "/lab-summaries/" + quote(row["review_id"], safe="")
        items.append(
            "<li><a href=\"" + escape(href) + "\">" + escape(row["patient_id"])
            + "</a> " + escape(label) + "</li>")
    return "<ul>" + "".join(items) + "</ul>"


def _detail(case):
    summary = case["summary"]
    parts = [
        _home(),
        "<dl>",
        _pair("Paciente", case["patient_id"]),
        _pair("Estado original", case["status"]),
        _pair("Operación", summary.get("kind") or ""),
        _pair("Revisión del modelo", summary.get("review") or ""),
    ]
    receipt = case["receipt"] or {}
    for label, key in (
        ("Proveedor", "provider"), ("Modelo", "model"), ("Fase", "phase"),
        ("Solicitudes", "requests_sent"), ("Registrado", "recorded_at"),
        ("Identificador de solicitud", "provider_request_id"),
    ):
        if key in receipt and receipt[key] is not None:
            parts.append(_pair(label, receipt[key]))
    parts.append("</dl><p>El texto siguiente es la salida del modelo. No reinterpreta valueQuantity ni convierte unidades.</p><h2>Resumen generado</h2>")
    for statement in summary.get("statements") or []:
        parts.append("<p>" + escape(statement.get("text") or "") + "</p>")
    parts.append("<h2>Observaciones citadas</h2><ul>")
    for source in case["sources"]:
        parts.append(
            "<li>" + escape(source["source"]) + " " + escape(source["resourceType"])
            + " " + escape(source["id"]) + "</li>")
    parts.append("</ul>")
    decision = case["decision"]
    if decision is None:
        parts.append(_form(case["review_id"]))
    else:
        parts.append("<h2>Decisión</h2><dl>")
        parts.append(_pair("Resultado", decision["decision"]))
        parts.append(_pair("Revisor", decision["reviewer_id"]))
        parts.append(_pair("Fecha", decision["decided_at"]))
        parts.append(_pair("Observación", decision["note"]))
        parts.append("</dl>")
    if case["decision_audit"]:
        parts.append("<h2>Auditoría</h2><ul>")
        for item in case["decision_audit"]:
            parts.append(
                "<li>" + escape(item["actor_id"]) + " " + escape(item["decision"])
                + " " + escape(item["outcome"]) + "</li>")
        parts.append("</ul>")
    return "".join(parts)


def _form(review_id):
    action = "/lab-summaries/" + quote(review_id, safe="") + "/decision"
    return (
        "<form method=\"post\" action=\"" + escape(action) + "\">"
        "<label>Observación del revisor <input name=\"note\" maxlength=\"400\" required></label>"
        "<button type=\"submit\" name=\"decision\" value=\"approved\">Aprobar</button>"
        "<button type=\"submit\" name=\"decision\" value=\"rejected\">Rechazar</button>"
        "</form>"
    )


def _pair(label, value):
    return "<dt>" + escape(str(label)) + "</dt><dd>" + escape(str(value)) + "</dd>"


def _home():
    return "<p><a href=\"/lab-summaries\">Bandeja</a></p>"


def _p(message):
    return "<p>" + escape(message) + "</p>"


def _page(title, body):
    return (
        "<!DOCTYPE html>\n<html lang=\"es\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<title>" + escape(title) + "</title>\n"
        "<link rel=\"stylesheet\" href=\"/review-static/review.css\">\n"
        "</head>\n<body>\n<h1>" + escape(title) + "</h1>\n" + body + "\n</body>\n</html>\n"
    )


def _html(content, status_code=200):
    return HTMLResponse(content=content, status_code=status_code, headers={"Cache-Control": "no-store"})
