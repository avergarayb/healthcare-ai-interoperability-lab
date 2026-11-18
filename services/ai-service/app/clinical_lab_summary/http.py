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

from .iam_http import LabAccess, hmac_equal, require_lab_access
from .review import (
    IamReviewer, ReviewError, Reviewer, decide, list_reviews, read_review,
    review_organization, reviews_for_organization,
)


_UCUM = "http://unitsofmeasure.org"
_UNIT_FOR_CODE = {"mm[Hg]": "mmHg"}
_STATES = {"", "pending", "approved", "rejected"}
_LABELS = {"pending": "Pendiente", "approved": "Aprobado", "rejected": "Rechazado"}


def render_lab_summary_queue(request: Request, settings: Settings) -> Response:
    access = require_lab_access(request, settings)
    if isinstance(access, Response):
        return access
    path = _path(settings)
    if path is None:
        return _html(_page(access, "Resúmenes de laboratorio", _p("El almacén de revisión no está configurado."), "bandeja"), 503)
    try:
        rows = list_reviews(path)
    except ReviewError:
        return _html(_page(access, "Resúmenes de laboratorio", _p("La revisión no está disponible."), "bandeja"), 503)
    if access.mode == "iam":
        if "read" not in access.permissions:
            rows = []
        else:
            allowed = reviews_for_organization(path, access.organization_id)
            rows = [row for row in rows if row["review_id"] in allowed]
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
    if access.mode == "iam" and "read" not in access.permissions:
        body = _p("Su rol no incluye la consulta de resúmenes.") + body
    return _html(_page(access, "Resúmenes de laboratorio", body, "bandeja"))


def render_lab_summary(request: Request, settings: Settings, review_id: str) -> Response:
    access = require_lab_access(request, settings)
    if isinstance(access, Response):
        return access
    path = _path(settings)
    if path is None:
        return _html(_page(access, "Resumen", _p("El almacén de revisión no está configurado."), "bandeja"), 503)
    if access.mode == "iam":
        denied = _iam_read(access, path, review_id)
        if denied is not None:
            return _html(_page(access, "Resumen", denied, "detalle"), 403)
    try:
        case = read_review(path, review_id)
        case["organization_id"] = review_organization(path, review_id) or ""
    except ReviewError as error:
        status = 404 if error.reason == "not_found" else 503
        return _html(_page(access, "Resumen", _p("El resumen no está disponible."), "bandeja"), status)
    return _html(_page(access, "Resumen de laboratorio", _detail(case, access), "detalle"))


def submit_lab_summary_decision(
    request: Request, settings: Settings, review_id: str, raw_body: bytes, content_type: str | None,
) -> Response:
    access = require_lab_access(request, settings)
    if isinstance(access, Response):
        return access
    path = _path(settings)
    if path is None:
        return _html(_page(access, "Resumen", _p("El almacén de revisión no está configurado."), "bandeja"), 503)
    if not _same_origin(request):
        return _html(_page(access, "Resumen", _p("La decisión no fue aceptada."), "bandeja"), 403)
    fields = _fields(raw_body, content_type, iam=access.mode == "iam")
    if fields is None:
        return _html(_page(access, "Resumen", _p("La decisión no fue aceptada."), "bandeja"), 422)
    if access.mode == "iam":
        if "decide" not in access.permissions or not hmac_equal(fields["csrf"], access.csrf):
            return _html(_page(access, "Resumen", _p("No tiene permiso para registrar esta decisión."), "detalle"), 403)
        reviewer = IamReviewer(
            access.principal_id, access.issuer, access.subject, access.organization_id,
            access.role, access.session_id)
    else:
        reviewer = Reviewer(access.principal_id, access.authenticator_id, access.session_id)
    try:
        decide(
            path, review_id, reviewer, fields["decision"], fields["note"],
            datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"))
    except ReviewError as error:
        if error.reason == "already_decided":
            return _html(_page(access, "Resumen", _p("Este resumen ya tiene una decisión."), "bandeja"), 409)
        if error.reason in {"reviewer_denied", "role_denied", "organization_denied"}:
            return _html(_page(access, "Resumen", _p("No tiene permiso para registrar esta decisión."), "bandeja"), 403)
        if error.reason == "schema_unprepared":
            return _html(_page(access, "Resumen", _p("Falta la preparación explícita del almacén de decisiones."), "bandeja"), 503)
        status = 404 if error.reason == "not_found" else 422
        return _html(_page(access, "Resumen", _p("La decisión no fue aceptada."), "bandeja"), status)
    return RedirectResponse("/lab-summaries/" + quote(review_id, safe=""), status_code=303)


def _path(settings):
    value = settings.lab_summary_review_db_path
    if type(value) is not str or value.strip() == "":
        return None
    return value


def _iam_read(access: LabAccess, path, review_id):
    if "read" not in access.permissions:
        return _p("No tiene acceso a este resumen.")
    if review_organization(path, review_id) != access.organization_id:
        return _p("No tiene acceso a este resumen.")
    return None


def _fields(raw_body, content_type, iam=False):
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
        allowed = {"decision", "note", "csrf"} if iam else {"decision", "note"}
        if key in fields or key not in allowed:
            return None
        fields[key] = value
    expected = {"decision", "note", "csrf"} if iam else {"decision", "note"}
    if set(fields) != expected:
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


def _detail(case, access):
    summary = case["summary"]
    parts = [
        "<section class=\"panel\"><h2>Registro</h2><dl>",
        _pair("Paciente", case["patient_id"]),
        _pair("Estado original", case["status"]),
        _pair("Operación", summary.get("kind") or ""),
        _pair("Revisión del modelo", summary.get("review") or ""),
    ]
    if case.get("organization_id"):
        parts.append(_pair("Organización", case["organization_id"]))
    evidence = case.get("clinical_evidence") or []
    if evidence:
        first = evidence[0]
        parts.append(_pair("Perfil aplicado", first.get("profile_id") or ""))
        parts.append(_pair("Versión del perfil", first.get("profile_version") or ""))
        parts.append(_pair("Clase de validación", first.get("validation_class") or ""))
    receipt = case["receipt"] or {}
    for label, key in (
        ("Proveedor", "provider"), ("Modelo", "model"), ("Fase", "phase"),
        ("Solicitudes", "requests_sent"),
        ("Registrado (fecha del archivo de recibo)", "recorded_at"),
        ("Identificador de solicitud", "provider_request_id"),
    ):
        if key in receipt and receipt[key] is not None:
            parts.append(_pair(label, receipt[key]))
    parts.append("</dl>")
    if evidence:
        parts.append(
            "<p class=\"warning\">El perfil aplicado es una regla interna de demostración. "
            "Esta validación no constituye conformidad RENHICE, HCDSNS ni EHDS, "
            "ni un documento IPS completo.</p>")
    if receipt.get("phase") == "intercepted":
        parts.append(
            "<p class=\"warning\">Esta ejecución usó el transporte Gemini interceptado. "
            "No es una respuesta del proveedor real.</p>")
    parts.append("</section>")
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
    if evidence:
        parts.append(_clinical_evidence(evidence))
    longitudinal = case.get("longitudinal_evidence") or []
    if longitudinal:
        parts.append(_longitudinal(longitudinal[0]))
    parts.append(_observations(case["sources"], verified=bool(evidence or longitudinal)))
    parts.append(_decision_block(case, access))
    parts.append(_audit(case))
    return "".join(parts)


def _clinical_evidence(evidence):
    rows = [
        "<tr><th scope=\"col\">Fuente</th><th scope=\"col\">Recurso</th><th scope=\"col\">Código</th>"
        "<th scope=\"col\">Valor</th><th scope=\"col\">UCUM</th><th scope=\"col\">Estado</th>"
        "<th scope=\"col\">Procedencia</th></tr>"
    ]
    for item in evidence:
        rows.append(
            "<tr><td>" + escape(item["source"]) + "</td><td>" + escape(item["resource_id"])
            + "</td><td>" + escape(item["code"]) + "</td><td>" + escape(item["value"])
            + "</td><td>" + escape(item["ucum_system"] + " " + item["ucum_code"])
            + "</td><td>" + escape(item["status"]) + "</td><td>" + escape(item["provenance_ref"])
            + "</td></tr>")
    return (
        "<section class=\"panel\"><h2>Observaciones verificadas</h2>"
        "<p>Estos valores salen de los recursos clínicos validados. "
        "No se reconstruyen desde el texto del modelo.</p>"
        "<div class=\"table-scroll\"><table><caption>Evidencia citada</caption>"
        + "".join(rows) + "</table></div></section>")


def _longitudinal(item):
    return (
        "<section class=\"panel\"><h2>Comparación longitudinal</h2><dl>"
        + _pair("Resultado anterior", item["prior_value"] + " " + item["ucum_code"])
        + _pair("Fecha anterior", item["prior_date"])
        + _pair("Fuente anterior", item["prior_provenance"])
        + _pair("Resultado reciente", item["recent_value"] + " " + item["ucum_code"])
        + _pair("Fecha reciente", item["recent_date"])
        + _pair("Fuente reciente", item["recent_provenance"])
        + _pair("Cambio calculado", item["absolute_difference"] + " " + item["ucum_code"])
        + _pair("Dirección", item["direction"])
        + _pair("Código", item["code"])
        + _pair("UCUM", item["ucum_system"] + " " + item["ucum_code"])
        + _pair("Comparabilidad", item["comparability"])
        + "</dl><p>El cambio lo calculó el motor determinista. "
        "El texto del modelo no es la fuente de estos valores.</p></section>"
    )


def _observations(sources, verified=False):
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
    if "absent" in kinds and not verified:
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


def _decision_block(case, access):
    decision = case["decision"]
    if decision is None:
        if access.mode == "iam" and "decide" not in access.permissions:
            return "<section class=\"panel\"><h2>Revisión humana</h2>" + _p(
                "Su rol no incluye aprobar ni rechazar este resumen.") + "</section>"
        return _form(case["review_id"], access.csrf if access.mode == "iam" else "")
    identity = case.get("identity") or {}
    parts = [
        "<section class=\"panel\"><h2>Decisión humana</h2><dl>",
        _pair("Resultado", decision["decision"]),
        _pair("Revisor", decision["reviewer_id"]),
        _pair("Fecha", decision["decided_at"]),
        _pair("Observación", decision["note"]),
    ]
    if identity:
        parts.extend([
            _pair("Emisor", identity["issuer"]),
            _pair("Sujeto", identity["subject"]),
            _pair("Organización", identity["organization_id"]),
            _pair("Rol", identity["role"]),
        ])
    parts.append("</dl></section>")
    return "".join(parts)


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


def _form(review_id, csrf=""):
    action = "/lab-summaries/" + quote(review_id, safe="") + "/decision"
    hidden = ""
    notice = (
        "La identidad del revisor sale de la sesión del servidor. "
        "Esta autenticación de desarrollo no es seguridad de producción."
    )
    if csrf:
        hidden = "<input type=\"hidden\" name=\"csrf\" value=\"" + escape(csrf) + "\">"
        notice = (
            "La identidad del revisor sale de la sesión validada por el servidor. "
            "Un campo del navegador no cambia el rol ni la organización."
        )
    return (
        "<section class=\"panel\"><h2>Revisión humana</h2>"
        "<p>" + notice + "</p>"
        "<form class=\"decision\" method=\"post\" action=\"" + escape(action) + "\">"
        + hidden +
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
    if getattr(session, "mode", "") == "iam":
        disclaimer = "Sesión OIDC de laboratorio. No es certificación ni IAM sanitario de producción."
        header = (
            "<header class=\"identity\"><p>" + escape(session.display_name) + "</p>"
            "<p>" + escape(session.organization_id) + "</p><p>" + escape(session.role) + "</p>"
            "<form method=\"post\" action=\"/lab-review-iam/logout\">"
            "<input type=\"hidden\" name=\"csrf\" value=\"" + escape(session.csrf) + "\">"
            "<button type=\"submit\">Cerrar sesión</button></form></header>"
        )
    else:
        disclaimer = "Sesión de desarrollo. No es autenticación clínica de producción."
        header = "<header><p>Sesión de desarrollo</p><p>" + principal + "</p></header>"
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
        "<p class=\"disclaimer\">" + escape(disclaimer) + "</p>\n"
        "<nav aria-label=\"Secciones\">\n"
        "<a href=\"/lab-summaries\"" + bandeja + ">Bandeja</a>\n"
        "<a href=\"/lab-summaries#historial\">Historial</a>\n"
        "</nav>\n</aside>\n<div class=\"lab-main\">\n"
        + header + "\n"
        "<main id=\"contenido\">\n<h1>" + escape(title) + "</h1>\n" + body + "\n</main>\n"
        "</div>\n</div>\n</body>\n</html>\n"
    )


def _html(content, status_code=200):
    return HTMLResponse(content=content, status_code=status_code, headers={"Cache-Control": "no-store"})
