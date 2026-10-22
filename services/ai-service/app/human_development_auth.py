"""Development-only login and the review-session gate.

A session cookie is not service authorization and is not clinician authorization.
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import logging
import re
import time
from datetime import datetime, timezone
from html import escape
from urllib.parse import parse_qsl

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from app.config import Settings
from app.human_session import (
    DEVELOPMENT_AUTHENTICATOR_V1,
    SESSION_TTL_SECONDS,
    HumanPrincipal,
    HumanSession,
    HumanSessionRejected,
    HumanSessionService,
    HumanSessionStoreInitializationError,
    HumanSessionUnavailable,
    hash_session_token,
    validate_human_principal,
)
from app.human_session_sqlite import SQLiteHumanSessionRepository


log = logging.getLogger("ai-service.human_login")

SESSION_COOKIE = "human_review_session"
LOGIN_BODY_LIMIT = 1024
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1"})
_PRINCIPAL_ID = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")
MSG_SIGN_IN_FAILED = "Sign-in failed."
MSG_UNAVAILABLE = "This demo is not available."


class DevelopmentAuthenticationFailed(Exception):
    """The presented development secret did not match."""


class DevelopmentAuthenticator:
    """Checks the configured development secret and returns the fixed principal."""

    def __init__(self, *, principal: HumanPrincipal, secret: str) -> None:
        self._principal = validate_human_principal(principal)
        self._secret = secret

    def __repr__(self) -> str:
        return f"DevelopmentAuthenticator(principal_id={self._principal.principal_id!r})"

    @property
    def principal(self) -> HumanPrincipal:
        return self._principal

    def authenticate(self, presented_secret: str) -> HumanPrincipal:
        if not isinstance(presented_secret, str) or not _secret_matches(self._secret, presented_secret):
            raise DevelopmentAuthenticationFailed
        return self._principal


def development_authenticator(settings: Settings) -> DevelopmentAuthenticator | None:
    """Return the authenticator only when every local-development guard passes."""
    if settings.human_review_development_auth_enabled is not True:
        return None
    if settings.host not in _LOOPBACK_HOSTS:
        return None
    secret = settings.human_review_development_auth_secret
    if not isinstance(secret, str) or len(secret) < 32:
        return None
    if secret == settings.model_boundary_service_token or secret == settings.human_review_form_signing_secret:
        return None
    principal_id = settings.human_review_development_principal_id
    display_name = settings.human_review_development_principal_display_name
    if not isinstance(principal_id, str) or _PRINCIPAL_ID.fullmatch(principal_id) is None:
        return None
    if not isinstance(display_name, str) or not _valid_display_name(display_name):
        return None
    session_path = settings.human_session_db_path
    if (
        not isinstance(session_path, str)
        or not session_path.strip()
        or session_path == ":memory:"
        or session_path == settings.ai_review_db_path
        or session_path == settings.institutional_knowledge_db_path
    ):
        return None
    principal = HumanPrincipal(
        principal_id=principal_id,
        display_name=display_name,
        authenticator_id=DEVELOPMENT_AUTHENTICATOR_V1,
    )
    try:
        validate_human_principal(principal)
    except ValueError:
        return None
    return DevelopmentAuthenticator(principal=principal, secret=secret)


def listener_is_loopback(request: Request) -> bool:
    """True only for the local address of the accepted socket.

    Uvicorn copies that address from getsockname() into scope["server"].
    It is not AI_SERVICE_HOST and it is not the Host header.
    """
    server = request.scope.get("server")
    if not isinstance(server, (list, tuple)) or not server:
        return False
    host = server[0]
    if not isinstance(host, str):
        return False
    if host.startswith("[") and host.endswith("]"):
        host = host[1:-1]
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        return bool(address.ipv4_mapped.is_loopback)
    return bool(address.is_loopback)


def _request_authenticator(request: Request, settings: Settings) -> DevelopmentAuthenticator | None:
    if not listener_is_loopback(request):
        return None
    return development_authenticator(settings)


def render_development_login(request: Request, settings: Settings) -> Response:
    started = time.perf_counter()
    status = 404
    result = "hidden"
    try:
        if _request_authenticator(request, settings) is None:
            return _html(_page("Review", _p(MSG_UNAVAILABLE)), status)
        status = 200
        result = "form"
        return _html(_page("Sign in", _login_form()), status)
    finally:
        _log("/review-login", status, result, started)


def submit_development_login(
    request: Request,
    settings: Settings,
    raw_body: bytes,
    content_type: str | None,
) -> Response:
    started = time.perf_counter()
    status = 400
    result = "denied"
    try:
        authenticator = _request_authenticator(request, settings)
        if authenticator is None:
            status = 404
            result = "hidden"
            return _html(_page("Review", _p(MSG_UNAVAILABLE)), status)
        if not _same_origin(request):
            return _html(_page("Sign in", _p(MSG_SIGN_IN_FAILED)), status)
        fields = _login_fields(raw_body, content_type)
        if fields is None:
            return _html(_page("Sign in", _p(MSG_SIGN_IN_FAILED)), status)
        repository = _session_repository(request, settings)
        if repository is None:
            status = 503
            result = "unavailable"
            return _html(_page("Sign in", _p(MSG_UNAVAILABLE)), status)
        try:
            principal = authenticator.authenticate(fields["developmentSecret"])
        except DevelopmentAuthenticationFailed:
            status = 401
            return _html(_page("Sign in", _p(MSG_SIGN_IN_FAILED)), status)
        service = HumanSessionService(repository, clock=_clock(request))
        try:
            issued = service.issue(principal)
        except HumanSessionUnavailable:
            status = 503
            result = "unavailable"
            return _html(_page("Sign in", _p(MSG_UNAVAILABLE)), status)
        status = 303
        result = "accepted"
        response = RedirectResponse(
            url="/review-cases",
            status_code=303,
            headers={"Cache-Control": "no-store"},
        )
        _set_session_cookie(response, request, issued.token)
        return response
    finally:
        _log("/review-login", status, result, started)


def submit_development_logout(
    request: Request,
    settings: Settings,
    raw_body: bytes,
    content_type: str | None,
) -> Response:
    started = time.perf_counter()
    status = 400
    result = "denied"
    try:
        if _request_authenticator(request, settings) is None:
            status = 404
            result = "hidden"
            return _html(_page("Review", _p(MSG_UNAVAILABLE)), status)
        if not _same_origin(request):
            return _html(_page("Sign in", _p(MSG_SIGN_IN_FAILED)), status)
        if raw_body:
            status = 400
            return _html(_page("Sign in", _p(MSG_SIGN_IN_FAILED)), status)
        token = request.cookies.get(SESSION_COOKIE)
        if token:
            try:
                hash_session_token(token)
            except HumanSessionRejected:
                status = 303
                result = "rejected"
                return _clear_and_redirect(request)
        if not token:
            status = 303
            result = "rejected"
            return _clear_and_redirect(request)
        repository = _session_repository(request, settings)
        if repository is None:
            status = 503
            result = "unavailable"
            return _html(_page("Sign in", _p(MSG_UNAVAILABLE)), status)
        service = HumanSessionService(repository, clock=_clock(request))
        try:
            service.resolve(token)
        except HumanSessionRejected:
            status = 303
            result = "rejected"
            return _clear_and_redirect(request)
        except HumanSessionUnavailable:
            status = 503
            result = "unavailable"
            return _html(_page("Sign in", _p(MSG_UNAVAILABLE)), status)
        try:
            service.revoke(token)
        except HumanSessionUnavailable:
            status = 503
            result = "unavailable"
            return _html(_page("Sign in", _p(MSG_UNAVAILABLE)), status)
        status = 303
        result = "accepted"
        return _clear_and_redirect(request)
    finally:
        _log("/review-logout", status, result, started)


def require_human_session(request: Request, settings: Settings) -> HumanSession | Response:
    """Resolve the live session for a review route, or the failure response.

    The returned session is the server record. Request fields are not a principal.
    """
    if _request_authenticator(request, settings) is None:
        return _html(_page("Review", _p(MSG_UNAVAILABLE)), 503)
    repository = _session_repository(request, settings)
    if repository is None:
        return _html(_page("Review", _p(MSG_UNAVAILABLE)), 503)
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return _clear_and_redirect(request)
    service = HumanSessionService(repository, clock=_clock(request))
    try:
        return service.resolve(token)
    except HumanSessionRejected:
        return _clear_and_redirect(request)
    except HumanSessionUnavailable:
        return _html(_page("Review", _p(MSG_UNAVAILABLE)), 503)


def _secret_matches(configured: str, presented: str) -> bool:
    return hmac.compare_digest(
        hashlib.sha256(configured.encode("utf-8")).digest(),
        hashlib.sha256(presented.encode("utf-8")).digest(),
    )


def _valid_display_name(value: str) -> bool:
    if not 1 <= len(value) <= 80:
        return False
    return all(ord(character) >= 32 and ord(character) != 127 for character in value)


def _same_origin(request: Request) -> bool:
    origin = request.headers.get("origin")
    if origin is None or origin == "":
        return False
    return origin == f"{request.url.scheme}://{request.url.netloc}"


def _login_fields(raw_body: bytes, content_type: str | None) -> dict[str, str] | None:
    if len(raw_body) > LOGIN_BODY_LIMIT:
        return None
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
        if key != "developmentSecret" or key in fields:
            return None
        fields[key] = value
    if set(fields) != {"developmentSecret"}:
        return None
    return fields


def _session_repository(request: Request, settings: Settings):
    if hasattr(request.app.state, "human_session_repository"):
        return request.app.state.human_session_repository
    try:
        repository = SQLiteHumanSessionRepository(settings.human_session_db_path)
        repository.initialize()
    except HumanSessionStoreInitializationError:
        return None
    request.app.state.human_session_repository = repository
    return repository


def _clock(request: Request):
    clock = getattr(request.app.state, "human_session_clock", None)
    if clock is None:
        return lambda: datetime.now(timezone.utc)
    return clock


def _set_session_cookie(response: Response, request: Request, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        samesite="strict",
        path="/",
        secure=request.url.scheme == "https",
    )


def _clear_and_redirect(request: Request) -> RedirectResponse:
    response = RedirectResponse(
        url="/review-login",
        status_code=303,
        headers={"Cache-Control": "no-store"},
    )
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        httponly=True,
        samesite="strict",
        secure=request.url.scheme == "https",
    )
    return response


def _login_form() -> str:
    return (
        "<form method=\"post\" action=\"/review-login\">"
        '<input type="password" name="developmentSecret" autocomplete="off">'
        '<button type="submit">Sign in</button>'
        "</form>"
    )


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


def _html(content: str, status_code: int) -> HTMLResponse:
    return HTMLResponse(content=content, status_code=status_code, headers={"Cache-Control": "no-store"})


def _p(message: str) -> str:
    return f"<p>{esc(message)}</p>"


def esc(value: str) -> str:
    return escape(value, quote=True)


def _log(route: str, status: int, result: str, started: float) -> None:
    duration_ms = int((time.perf_counter() - started) * 1000)
    log.info(
        "human_login route=%s status=%s result=%s durationMs=%s",
        route,
        status,
        result,
        duration_ms,
    )
