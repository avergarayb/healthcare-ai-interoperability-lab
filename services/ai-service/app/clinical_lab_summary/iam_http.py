"""HTTP boundary for the laboratory review OIDC session."""
from dataclasses import dataclass
from html import escape
from urllib.parse import parse_qsl

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from app.config import Settings
from app.human_development_auth import require_human_session

from .iam import (
    SESSION_COOKIE, TRANSACTION_COOKIE, IamRejected, _client, begin_authentication,
    clock_now, complete_authentication, end_session_url, load_config, resolve_session, revoke_session,
)


@dataclass(frozen=True)
class LabAccess:
    mode: str
    principal_id: str
    display_name: str
    authenticator_id: str
    organization_id: str
    role: str
    issuer: str
    subject: str
    session_id: str
    csrf: str
    permissions: frozenset


def require_lab_access(request: Request, settings: Settings) -> LabAccess | Response:
    if not settings.lab_review_iam_enabled:
        session = require_human_session(request, settings)
        if isinstance(session, Response):
            return session
        return LabAccess(
            "development", session.principal_id, session.display_name, session.authenticator_id,
            "", "", "", "", session.session_id, "", frozenset({"read", "decide", "audit"}))
    try:
        config = load_config(settings)
    except IamRejected:
        return _page("Acceso no disponible", "La configuración de identidad no es aceptable.", 503)
    now = clock_now(request)
    token = request.cookies.get(SESSION_COOKIE, "")
    session = resolve_session(config, token, now) if token else None
    if session is None:
        return _redirect("/lab-review-iam/login?reason=" + ("expired" if token else "required"))
    from .review import iam_principal_id
    return LabAccess(
        "iam", iam_principal_id(session.issuer, session.subject), session.display_name,
        "LAB_REVIEW_IAM_V1", session.organization_id, session.role, session.issuer, session.subject,
        session.session_id, session.csrf, session.permissions)


def render_iam_login(request: Request, settings: Settings) -> Response:
    denied = _configured(settings)
    if denied is not None:
        return denied
    reason = request.query_params.get("reason") or ""
    message = {
        "expired": "La sesión venció. Vuelva a ingresar.",
        "signed-out": "La sesión se cerró.",
        "denied": "El proveedor no autorizó el ingreso.",
    }.get(reason, "Ingrese con el proveedor de identidad del laboratorio.")
    body = (
        "<p>" + escape(message) + "</p>"
        "<form method=\"post\" action=\"/lab-review-iam/start\">"
        "<button type=\"submit\">Continuar al proveedor</button></form>"
        "<p>Esta autenticación de laboratorio no es certificación sanitaria ni IAM de producción. "
        "En 127.0.0.1 el proveedor y la cookie de un solo uso pueden usar HTTP con el atributo Secure; "
        "esa excepción no es aceptable en producción.</p>"
    )
    return _page("Ingreso", body)


def start_iam_login(request: Request, settings: Settings) -> Response:
    denied = _configured(settings)
    if denied is not None:
        return denied
    if not _same_origin(request):
        return _page("Ingreso", "El ingreso no fue aceptado.", 403)
    try:
        config = load_config(settings)
        client = getattr(request.app.state, "lab_review_iam_http", None)
        url, state = begin_authentication(config, clock_now(request), client)
    except IamRejected:
        return _page("Ingreso", "El proveedor de identidad no está disponible.", 503)
    response = RedirectResponse(url, status_code=303, headers={"Cache-Control": "no-store"})
    _set_cookie(response, request, TRANSACTION_COOKIE, state, 300)
    return response


def finish_iam_login(request: Request, settings: Settings, raw_body: bytes, content_type: str | None) -> Response:
    denied = _configured(settings)
    if denied is not None:
        return denied
    if request.method != "POST":
        return _redirect("/lab-review-iam/login?reason=denied")
    fields = _callback_fields(request, raw_body, content_type)
    if fields is None:
        return _redirect("/lab-review-iam/login?reason=denied")
    cookie_state = request.cookies.get(TRANSACTION_COOKIE, "")
    if not cookie_state or cookie_state != fields["state"]:
        return _redirect("/lab-review-iam/login?reason=denied")
    try:
        config = load_config(settings)
        client = getattr(request.app.state, "lab_review_iam_http", None) or _client(config)
        try:
            token, _session = complete_authentication(
                config, fields["state"], fields["code"], clock_now(request), client)
        finally:
            if not hasattr(request.app.state, "lab_review_iam_http"):
                client.close()
    except IamRejected:
        response = _redirect("/lab-review-iam/login?reason=denied")
        _clear_cookie(response, request, TRANSACTION_COOKIE)
        return response
    response = _redirect("/lab-summaries")
    _clear_cookie(response, request, TRANSACTION_COOKIE)
    _set_cookie(response, request, SESSION_COOKIE, token, 1800)
    return response


def submit_iam_logout(request: Request, settings: Settings, raw_body: bytes, content_type: str | None) -> Response:
    denied = _configured(settings)
    if denied is not None:
        return denied
    if not _same_origin(request):
        return _page("Sesión", "El cierre de sesión no fue aceptado.", 403)
    fields = _logout_fields(raw_body, content_type)
    try:
        config = load_config(settings)
    except IamRejected:
        return _page("Sesión", "La configuración de identidad no es aceptable.", 503)
    token = request.cookies.get(SESSION_COOKIE, "")
    session = resolve_session(config, token, clock_now(request)) if token else None
    if fields is None or session is None or not hmac_equal(fields["csrf"], session.csrf):
        return _page("Sesión", "El cierre de sesión no fue aceptado.", 403)
    revoke_session(config, token, clock_now(request))
    try:
        provider_logout = end_session_url(config, getattr(request.app.state, "lab_review_iam_http", None))
    except IamRejected:
        provider_logout = None
    response = _redirect(provider_logout or "/lab-review-iam/login?reason=signed-out")
    _clear_cookie(response, request, SESSION_COOKIE)
    return response


def hmac_equal(left: str, right: str) -> bool:
    import hmac
    if not isinstance(left, str) or not isinstance(right, str) or len(left) != len(right):
        return False
    return hmac.compare_digest(left, right)


def _configured(settings: Settings):
    if not settings.lab_review_iam_enabled:
        return _page("Acceso no disponible", "La identidad empresarial no está habilitada.", 404)
    try:
        load_config(settings)
    except IamRejected:
        return _page("Acceso no disponible", "La configuración de identidad no es aceptable.", 503)
    return None


def _callback_fields(request, raw_body, content_type):
    if request.method == "GET":
        state = request.query_params.get("state")
        code = request.query_params.get("code")
    else:
        if content_type is None or not content_type.startswith("application/x-www-form-urlencoded"):
            return None
        if len(raw_body) > 4096:
            return None
        try:
            pairs = parse_qsl(raw_body.decode("utf-8"), keep_blank_values=True, max_num_fields=6)
        except (UnicodeDecodeError, ValueError):
            return None
        fields = {}
        for key, value in pairs:
            if key in fields or key not in {"state", "code"}:
                continue
            fields[key] = value
        state = fields.get("state")
        code = fields.get("code")
    if not state or not code:
        return None
    return {"state": state, "code": code}


def _logout_fields(raw_body, content_type):
    if content_type is None or not content_type.startswith("application/x-www-form-urlencoded") or len(raw_body) > 512:
        return None
    try:
        pairs = parse_qsl(raw_body.decode("utf-8"), keep_blank_values=True, max_num_fields=2)
    except (UnicodeDecodeError, ValueError):
        return None
    fields = {}
    for key, value in pairs:
        if key in fields or key != "csrf":
            return None
        fields[key] = value
    if set(fields) != {"csrf"}:
        return None
    return fields


def _same_origin(request: Request) -> bool:
    origin = request.headers.get("origin")
    return origin == f"{request.url.scheme}://{request.url.netloc}"


def _set_cookie(response: Response, request: Request, name: str, value: str, max_age: int) -> None:
    samesite, secure = _cookie_policy(request, name)
    response.set_cookie(
        name, value, max_age=max_age, httponly=True, samesite=samesite, path="/", secure=secure)


def _clear_cookie(response: Response, request: Request, name: str) -> None:
    samesite, secure = _cookie_policy(request, name)
    response.delete_cookie(name, path="/", httponly=True, samesite=samesite, secure=secure)


def _cookie_policy(request: Request, name: str) -> tuple[str, bool]:
    if name == TRANSACTION_COOKIE:
        # Keycloak posts the code from another loopback port. Lax would drop this
        # single-use cookie. SameSite=None requires Secure; browsers accept that
        # combination on http://127.0.0.1 and reject it for any other HTTP host.
        return "none", True
    return "lax", request.url.scheme == "https"


def _redirect(url: str) -> RedirectResponse:
    response = RedirectResponse(url, status_code=303, headers={"Cache-Control": "no-store"})
    return response


def _page(title: str, body: str, status_code: int = 200) -> HTMLResponse:
    content = (
        "<!DOCTYPE html><html lang=\"es\"><head><meta charset=\"utf-8\">"
        "<title>" + escape(title) + "</title></head><body><h1>" + escape(title) + "</h1>"
        + body + "</body></html>"
    )
    return HTMLResponse(content, status_code=status_code, headers={"Cache-Control": "no-store"})
