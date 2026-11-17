"""Laboratory pages for one human decision on a lab summary.

The session principal is resolved by the existing development login. A posted
role is ignored because it is not accepted as a field. No model is called.
The page does not parse a model sentence into a quantity.
"""
from datetime import datetime, timezone
from html import escape
from urllib.parse import parse_qsl, quote

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from app.config import Settings
from app.human_development_auth import require_human_session

from .review import ReviewError, Reviewer, decide, list_reviews, read_review


_UCUM = "http://unitsofmeasure.org"
_UNIT_FOR_CODE = {"mm[Hg]": "mmHg"}
_STATES = {"", "pending", "approved", "rejected"}
_LABELS = {"pending": "Pendiente", "approved": "Aprobado", "rejected": "Rechazado"}


def render_lab_summary_queue(request: Request, settings: Settings) -> Response:
    session = require_human_session(request, settings)
    if isinstance(session, Response):
        return session
    path = _path(settings)
    if path is None:
        return _html(_page(session, "Resúmenes de laboratorio", _p("El almacén de revisión no está configurado."), "bandeja"), 503)
    try:
        rows = list_reviews(path)
    except ReviewError:
        return _html(_page(session, "Resúmenes de laboratorio", _p("La revisión no está disponible."), "bandeja"), 503)
    query, state = _filters(request)
    visible = [row for row in rows if _matches(row, query, state)]
    pending = [row for row in visible if row["decision"] is None]
    decided = [row for row in visible if row["decision"] is not None]
    body = _indicators(rows) + _filter_form(query, state)
    narrowed = bool(query or state)
    if state != "approved" and state != "rejected":
        body += "<h2>Pendientes</h2>" + _queue_table(
            pending, empty="Ningún resumen coincide con la búsqueda." if narrowed else "No hay resúmenes pendientes.")
    if state != "pending":
        body += "<h2 id=\"historial\">Historial de decisiones</h2>" + _history_table(
            decided, empty="Ningún resumen coincide con la búsqueda." if narrowed else "Todavía no hay decisiones.")
    return _html(_page(session, "Resúmenes de laboratorio", body, "bandeja"))


def render_lab_summary(request: Request, settings: Settings, review_id: str) -> Response:
    session = require_human_session(request, settings)
    if isinstance(session, Response):
        return session
    path = _path(settings)
    if path is None:
        return _html(_page(session, "Resumen", _p("El almacén de revisión no está configurado."), "bandeja"), 503)
    try:
        case = read_review(path, review_id)
    except ReviewError as error:
        status = 404 if error.reason == "not_found" else 503
        return _html(_page(session, "Resumen", _p("El resumen no está disponible."), "bandeja"), status)
    return _html(_page(session, "Resumen de laboratorio", _detail(case), "detalle"))


def submit_lab_summary_decision(
    request: Request, settings: Settings, review_id: str, raw_body: bytes, content_type: str | None,
) -> Response:
    session = require_human_session(request, settings)
    if isinstance(session, Response):
        return session
    path = _path(settings)
    if path is None:
        return _html(_page(session, "Resumen", _p("El almacén de revisión no está configurado."), "bandeja"), 503)
    if not _same_origin(request):
        return _html(_page(session, "Resumen", _p("La decisión no fue aceptada."), "bandeja"), 403)
    fields = _fields(raw_body, content_type)
    if fields is None:
        return _html(_page(session, "Resumen", _p("La decisión no fue aceptada."), "bandeja"), 422)
    try:
        reviewer = Reviewer(session.principal_id, session.authenticator_id, session.session_id)
        decide(
            path, review_id, reviewer, fields["decision"], fields["note"],
            datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"))
    except ReviewError as error:
        if error.reason == "already_decided":
            return _html(_page(session, "Resumen", _p("Este resumen ya tiene una decisión."), "bandeja"), 409)
        if error.reason == "reviewer_denied":
            return _html(_page(session, "Resumen", _p("El revisor no está autorizado."), "bandeja"), 403)
        if error.reason == "schema_unprepared":
            return _html(_page(session, "Resumen", _p("Falta la preparación explícita del almacén de decisiones."), "bandeja"), 503)
        status = 404 if error.reason == "not_found" else 422
        return _html(_page(session, "Resumen", _p("La decisión no fue aceptada."), "bandeja"), status)
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


def _filters(request):
    query = request.query_params.get("q") or ""
    state = request.query_params.get("estado") or ""
    if len(query) > 64:
        query = query[:64]
    if state not in _STATES:
        state = ""
    return query, state


def _matches(row, query, state):
    if state == "pending" and row["decision"] is not None:
        return False
    if state in {"approved", "rejected"} and row["decision"] != state:
        return False
    if query:
        haystack = " ".join((row["patient_id"], row["review_id"], row["authorization_id"])).lower()
        if query.casefold() not in haystack:
            return False
    return True


def _indicators(rows):
    counts = {
        "pending": sum(row["decision"] is None for row in rows),
        "approved": sum(row["decision"] == "approved" for row in rows),
        "rejected": sum(row["decision"] == "rejected" for row in rows),
    }
    cards = []
    for key in ("pending", "approved", "rejected"):
        href = "/lab-summaries?estado=" + key
        cards.append(
            "<a class=\"metric\" href=\"" + href + "\">"
            "<span>" + _LABELS[key] + "</span>"
            "<strong>" + str(counts[key]) + "</strong></a>")
    return "<section aria-label=\"Indicadores\" class=\"metrics\">" + "".join(cards) + "</section>"


def _filter_form(query, state):
    options = [("", "Todos"), ("pending", "Pendientes"), ("approved", "Aprobados"), ("rejected", "Rechazados")]
    choices = []
    for value, label in options:
        selected = " selected" if value == state else ""
        choices.append("<option value=\"" + escape(value) + "\"" + selected + ">" + escape(label) + "</option>")
    return (
        "<form class=\"filters\" method=\"get\" action=\"/lab-summaries\">"
        "<label>Buscar <input name=\"q\" maxlength=\"64\" value=\"" + escape(query) + "\"></label>"
        "<label>Estado <select name=\"estado\">" + "".join(choices) + "</select></label>"
        "<button type=\"submit\">Filtrar</button>"
        "</form>"
    )


def _queue_table(rows, empty):
    if not rows:
        return "<p class=\"empty\">" + escape(empty) + "</p>"
    items = [
        "<tr><th scope=\"col\">Paciente</th><th scope=\"col\">Estado</th>"
        "<th scope=\"col\">Autorización</th></tr>"
    ]
    for row in rows:
        href = "/lab-summaries/" + quote(row["review_id"], safe="")
        items.append(
            "<tr><td><a href=\"" + escape(href) + "\">" + escape(row["patient_id"]) + "</a></td>"
            "<td><span class=\"status pending\">Pendiente (pending)</span></td>"
            "<td>" + escape(row["authorization_id"]) + "</td></tr>")
    return "<div class=\"table-scroll\"><table><caption>Resúmenes sin decisión</caption>" + "".join(items) + "</table></div>"


def _history_table(rows, empty):
    if not rows:
        return "<p class=\"empty\">" + escape(empty) + "</p>"
    items = [
        "<tr><th scope=\"col\">Paciente</th><th scope=\"col\">Decisión</th>"
        "<th scope=\"col\">Fecha</th></tr>"
    ]
    for row in rows:
        href = "/lab-summaries/" + quote(row["review_id"], safe="")
        label = _LABELS.get(row["decision"], row["decision"] or "")
        items.append(
            "<tr><td><a href=\"" + escape(href) + "\">" + escape(row["patient_id"]) + "</a></td>"
            "<td><span class=\"status " + escape(row["decision"] or "") + "\">"
            + escape(label) + " (" + escape(row["decision"] or "") + ")</span></td>"
            "<td>" + escape(row["decided_at"] or "Sin fecha registrada") + "</td></tr>")
    return "<div class=\"table-scroll\"><table><caption>Decisiones registradas</caption>" + "".join(items) + "</table></div>"


def _detail(case):
    summary = case["summary"]
    parts = [
        "<section class=\"panel\"><h2>Registro</h2><dl>",
        _pair("Paciente", case["patient_id"]),
        _pair("Estado original", case["status"]),
        _pair("Operación", summary.get("kind") or ""),
        _pair("Revisión del modelo", summary.get("review") or ""),
    ]
    receipt = case["receipt"] or {}
    for label, key in (
        ("Proveedor", "provider"), ("Modelo", "model"), ("Fase", "phase"),
        ("Solicitudes", "requests_sent"),
        ("Registrado (fecha del archivo de recibo)", "recorded_at"),
        ("Identificador de solicitud", "provider_request_id"),
    ):
        if key in receipt and receipt[key] is not None:
            parts.append(_pair(label, receipt[key]))
    parts.append("</dl></section>")
    statements = summary.get("statements") or []
    parts.append(
        "<section class=\"panel model-text\"><h2>Texto original generado por el modelo</h2>"
        "<p>Este texto se muestra tal como quedó registrado. Está separado de las observaciones "
        "fuente y esta página no lo convierte en un valueQuantity.</p>")
    if any("GLU 141 mmol/L" in (statement.get("text") or "") for statement in statements):
        parts.append(
            "<p class=\"warning\">GLU 141 mmol/L es texto histórico generado por el modelo. "
            "Su unidad no está semánticamente validada y no se convierte ni se corrige.</p>")
    if not statements:
        parts.append("<p class=\"empty\">El registro no contiene texto del modelo.</p>")
    for statement in statements:
        parts.append("<p class=\"statement\">" + escape(statement.get("text") or "") + "</p>")
    parts.append("</section>")
    parts.append(_observations(case["sources"]))
    parts.append(_decision_block(case))
    parts.append(_audit(case))
    return "".join(parts)


def _observations(sources):
    parts = ["<section class=\"panel\"><h2>Referencias persistidas</h2>"]
    if not sources:
        parts.append("<p class=\"warning\">No hay referencias a observaciones en el registro.</p></section>")
        return "".join(parts)
    kinds = set()
    rows = [
        "<tr><th scope=\"col\">Fuente</th><th scope=\"col\">Tipo</th><th scope=\"col\">Identificador</th>"
        "<th scope=\"col\">Código</th><th scope=\"col\">Valor</th><th scope=\"col\">Unidad</th>"
        "<th scope=\"col\">Rango</th><th scope=\"col\">Semántica</th></tr>"
    ]
    for source in sources:
        view = _quantity_view(source)
        kinds.add(view["kind"])
        rows.append(
            "<tr><td>" + escape(source["source"]) + "</td><td>" + escape(source["resourceType"])
            + "</td><td>" + escape(source["id"]) + "</td><td>" + escape(view["code"])
            + "</td><td>" + escape(view["value"]) + "</td><td>" + escape(view["unit"])
            + "</td><td>" + escape(view["range"]) + "</td><td><span class=\"status "
            + escape(view["kind"]) + "\">" + escape(view["semantic"]) + "</span></td></tr>")
    if "absent" in kinds:
        parts.append(
            "<p class=\"warning\">Dato ausente. Hay una referencia sin valor ni unidad persistidos. "
            "Esta página no los toma del texto del modelo.</p>")
    if "unverified" in kinds:
        parts.append(
            "<p class=\"warning\">Unidad no verificable. El valor y la unidad se muestran como "
            "quedaron registrados. Esta página no los convierte ni los corrige.</p>")
    parts.append(
        "<div class=\"table-scroll\"><table><caption>Observaciones citadas</caption>"
        + "".join(rows) + "</table></div></section>")
    return "".join(parts)


def _quantity_view(source):
    """Separate a verified UCUM quantity, a stored unverifiable unit, and an absent field."""
    verified = _verified_quantity(source)
    if verified is not None:
        return {
            "code": verified["code"],
            "value": verified["value"],
            "unit": verified["unit"],
            "range": verified["range"] or "No registrado",
            "semantic": "UCUM verificable",
            "kind": "verified",
        }
    if "value" in source or "unit" in source:
        return {
            "code": _stored_text(source, "code"),
            "value": _stored_text(source, "value"),
            "unit": _stored_text(source, "unit"),
            "range": "No registrado",
            "semantic": "Unidad no verificable",
            "kind": "unverified",
        }
    return {
        "code": "No registrado",
        "value": "No registrado",
        "unit": "No registrado",
        "range": "No registrado",
        "semantic": "Dato ausente",
        "kind": "absent",
    }


def _stored_text(source, key):
    if key not in source:
        return "No registrado"
    value = source[key]
    if isinstance(value, bool) or value is None or value == "":
        return "No registrado"
    if type(value) in (int, float):
        return format(value, "g")
    if isinstance(value, str):
        return value
    return "No registrado"


def _verified_quantity(source):
    """Show a quantity only when the stored reference already carries a coherent UCUM value."""
    system = source.get("system")
    code = source.get("code")
    unit = source.get("unit")
    value = source.get("value")
    if system != _UCUM or not isinstance(code, str) or not code:
        return None
    expected = _UNIT_FOR_CODE.get(code, code)
    if unit != expected or type(value) not in (int, float) or isinstance(value, bool):
        return None
    low = source.get("range_low")
    high = source.get("range_high")
    reference = None
    if low is not None or high is not None:
        if (type(low) not in (int, float) or type(high) not in (int, float)
                or isinstance(low, bool) or isinstance(high, bool) or low > high):
            return None
        reference = format(low, "g") + "–" + format(high, "g") + " " + expected
    return {"code": code, "value": format(value, "g"), "unit": expected, "range": reference}


def _decision_block(case):
    decision = case["decision"]
    if decision is None:
        return _form(case["review_id"])
    return (
        "<section class=\"panel\"><h2>Decisión humana</h2><dl>"
        + _pair("Resultado", decision["decision"])
        + _pair("Revisor", decision["reviewer_id"])
        + _pair("Fecha", decision["decided_at"])
        + _pair("Observación", decision["note"])
        + "</dl></section>"
    )


def _audit(case):
    parts = ["<section class=\"panel\"><h2>Auditoría</h2>"]
    if not case["audit"] and not case["decision_audit"]:
        parts.append("<p class=\"empty\">No hay eventos de auditoría.</p></section>")
        return "".join(parts)
    parts.append("<ul>")
    for item in case["audit"]:
        parts.append("<li>Cola " + escape(item["event"]) + " " + escape(item["outcome"]) + "</li>")
    for item in case["decision_audit"]:
        parts.append(
            "<li>" + escape(item["actor_id"]) + " " + escape(item["decision"])
            + " " + escape(item["outcome"]) + "</li>")
    parts.append("</ul></section>")
    return "".join(parts)


def _form(review_id):
    action = "/lab-summaries/" + quote(review_id, safe="") + "/decision"
    return (
        "<section class=\"panel\"><h2>Revisión humana</h2>"
        "<p>La identidad del revisor sale de la sesión del servidor. "
        "Esta autenticación de desarrollo no es seguridad de producción.</p>"
        "<form class=\"decision\" method=\"post\" action=\"" + escape(action) + "\">"
        "<label>Observación del revisor "
        "<input name=\"note\" maxlength=\"400\" required></label>"
        "<label><input type=\"checkbox\" required> Confirmo esta decisión</label>"
        "<p id=\"decision-status\" role=\"status\"></p>"
        "<button type=\"submit\" name=\"decision\" value=\"approved\">Aprobar</button>"
        "<button type=\"submit\" name=\"decision\" value=\"rejected\">Rechazar</button>"
        "</form></section>"
        "<script>"
        "document.querySelector('form.decision').addEventListener('submit',function(event){"
        "var button=event.submitter;if(button){button.setAttribute('aria-busy','true');}"
        "var status=document.getElementById('decision-status');"
        "if(status){status.textContent='Registrando la decisión…';}});"
        "</script>"
    )


def _pair(label, value):
    return "<dt>" + escape(str(label)) + "</dt><dd>" + escape(str(value)) + "</dd>"


def _p(message):
    return "<p class=\"warning\">" + escape(message) + "</p>"


def _page(session, title, body, current):
    principal = escape(getattr(session, "principal_id", ""))
    bandeja = " aria-current=\"page\"" if current == "bandeja" else ""
    return (
        "<!DOCTYPE html>\n<html lang=\"es\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        "<title>" + escape(title) + "</title>\n"
        "<link rel=\"stylesheet\" href=\"/review-static/review.css\">\n"
        "<link rel=\"stylesheet\" href=\"/review-static/lab-review.css\">\n"
        "</head>\n<body class=\"lab-shell\">\n"
        "<a class=\"skip\" href=\"#contenido\">Saltar al contenido</a>\n"
        "<div class=\"lab-frame\">\n"
        "<aside>\n<p class=\"brand\">Revisión de laboratorio</p>\n"
        "<p class=\"disclaimer\">Sesión de desarrollo. No es autenticación clínica de producción.</p>\n"
        "<nav aria-label=\"Secciones\">\n"
        "<a href=\"/lab-summaries\"" + bandeja + ">Bandeja</a>\n"
        "<a href=\"/lab-summaries#historial\">Historial</a>\n"
        "</nav>\n</aside>\n<div class=\"lab-main\">\n"
        "<header><p>Sesión de desarrollo</p><p>" + principal + "</p></header>\n"
        "<main id=\"contenido\">\n<h1>" + escape(title) + "</h1>\n" + body + "\n</main>\n"
        "</div>\n</div>\n</body>\n</html>\n"
    )


def _html(content, status_code=200):
    return HTMLResponse(content=content, status_code=status_code, headers={"Cache-Control": "no-store"})
