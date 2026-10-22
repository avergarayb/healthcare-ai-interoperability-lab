from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.human_development_auth import SESSION_COOKIE
from app.human_session import (
    SESSION_TTL_SECONDS,
    HumanSessionRejected,
    HumanSessionService,
    HumanSessionUnavailable,
)
from app.human_session_sqlite import SQLiteHumanSessionRepository
from app.main import app, get_settings, review_cases


SECRET = "development-secret-value-32chars-min"
OTHER_SECRET = "another-development-secret-value-32"
SERVICE_TOKEN = "synthetic-service-token-a"
SIGNING_SECRET = "synthetic-form-signing-secret-b"
NOW = datetime(2026, 10, 7, 15, 0, tzinfo=timezone.utc)
ORIGIN = {"origin": "http://127.0.0.1"}


class Clock:
    def __init__(self, moment: datetime) -> None:
        self.moment = moment

    def __call__(self) -> datetime:
        return self.moment


def _settings(tmp_path: Path, **overrides) -> Settings:
    values = dict(
        model_boundary_base_url="http://model-boundary.test",
        model_boundary_path="/api/model-boundary/v1",
        model_boundary_timeout_seconds=5,
        model_boundary_service_token=SERVICE_TOKEN,
        human_review_form_signing_secret=SIGNING_SECRET,
        host="127.0.0.1",
        port=8090,
        ai_review_db_path=str(tmp_path / "review.sqlite3"),
        institutional_knowledge_db_path=str(tmp_path / "knowledge.sqlite3"),
        human_session_db_path=str(tmp_path / "human-session.sqlite3"),
        human_review_development_auth_enabled=True,
        human_review_development_auth_secret=SECRET,
        human_review_development_principal_id="lab-reviewer",
        human_review_development_principal_display_name="Lab reviewer",
    )
    values.update(overrides)
    return Settings(**values)


def _bind(settings: Settings, repository=None, clock: Clock | None = None) -> TestClient:
    app.dependency_overrides[get_settings] = lambda: settings
    if repository is not None:
        app.state.human_session_repository = repository
    if clock is not None:
        app.state.human_session_clock = clock
    return TestClient(app, base_url="http://127.0.0.1")


def _clear() -> None:
    app.dependency_overrides.clear()
    for name in ("human_session_repository", "human_session_clock"):
        if hasattr(app.state, name):
            delattr(app.state, name)


def _repository(tmp_path: Path) -> SQLiteHumanSessionRepository:
    repository = SQLiteHumanSessionRepository(tmp_path / "human-session.sqlite3")
    repository.initialize()
    return repository


def _login(client: TestClient, secret: str = SECRET, **kwargs):
    body = kwargs.pop("content", f"developmentSecret={secret}".encode("utf-8"))
    headers = {"content-type": "application/x-www-form-urlencoded", **ORIGIN, **kwargs.pop("headers", {})}
    return client.post("/review-login", content=body, headers=headers, follow_redirects=False, **kwargs)


def _cookie(response) -> str:
    header = response.headers["set-cookie"]
    pair = header.split(";", 1)[0]
    name, value = pair.split("=", 1)
    assert name == SESSION_COOKIE
    return value


def _rows(repository: SQLiteHumanSessionRepository):
    with sqlite3.connect(repository.database_path) as connection:
        connection.row_factory = sqlite3.Row
        return list(connection.execute("SELECT * FROM human_sessions").fetchall())


def test_successful_login_sets_a_session_cookie_and_review_requires_it(tmp_path, caplog):
    repository = _repository(tmp_path)
    client = _bind(_settings(tmp_path), repository)
    try:
        with caplog.at_level(logging.INFO):
            form = client.get("/review-login")
            posted = _login(client)
        assert form.status_code == 200
        assert 'name="developmentSecret"' in form.text
        assert SECRET not in form.text
        assert form.headers["cache-control"] == "no-store"
        assert "set-cookie" not in {name.lower() for name in form.headers}
        assert posted.status_code == 303
        assert posted.headers["location"] == "/review-cases"
        cookie = posted.headers["set-cookie"].lower()
        assert "httponly" in cookie
        assert "samesite=strict" in cookie
        assert "path=/" in cookie
        assert "max-age=28800" in cookie
        assert "secure" not in cookie
        token = _cookie(posted)
        assert token not in posted.text
        assert SECRET not in posted.text
        assert SECRET not in caplog.text
        assert token not in caplog.text
        rows = _rows(repository)
        assert len(rows) == 1
        assert rows[0]["principal_id"] == "lab-reviewer"
        assert rows[0]["token_hash"] != token
        assert token.encode("utf-8") not in repository.database_path.read_bytes()
        fresh = TestClient(app, base_url="http://127.0.0.1")
        queue = fresh.get("/review-cases", follow_redirects=False)
        assert queue.status_code == 303
        assert queue.headers["location"] == "/review-login"
        assert queue.headers["cache-control"] == "no-store"
        logged = TestClient(app, base_url="http://127.0.0.1")
        logged.cookies.set(SESSION_COOKIE, token)
        opened = logged.get("/review-cases")
        assert opened.headers.get("location") != "/review-login"
    finally:
        _clear()


def test_failed_login_creates_no_session(tmp_path):
    repository = _repository(tmp_path)
    client = _bind(_settings(tmp_path), repository)
    try:
        denied = _login(client, OTHER_SECRET)
        assert denied.status_code == 401
        assert denied.text.count("Sign-in failed.") == 1
        assert "set-cookie" not in {name.lower() for name in denied.headers}
        assert SECRET not in denied.text
        assert _rows(repository) == []
    finally:
        _clear()


def test_disabled_or_non_loopback_configuration_hides_login(tmp_path):
    path = tmp_path / "human-session.sqlite3"
    cases = [
        dict(human_review_development_auth_enabled=False),
        dict(host="0.0.0.0"),
        dict(host="localhost"),
        dict(human_review_development_auth_secret="short-secret"),
        dict(model_boundary_service_token=SECRET),
        dict(human_review_form_signing_secret=SECRET),
        dict(human_review_development_principal_id="Lab-Reviewer"),
        dict(human_review_development_principal_display_name="Lab\nreviewer"),
        dict(human_session_db_path=str(tmp_path / "review.sqlite3"), ai_review_db_path=str(tmp_path / "review.sqlite3")),
    ]
    try:
        for overrides in cases:
            _clear()
            client = _bind(_settings(tmp_path, **overrides))
            response = client.get("/review-login", headers={"x-forwarded-for": "127.0.0.1"})
            posted = _login(client)
            assert response.status_code == 404
            assert posted.status_code == 404
            assert "<form" not in response.text
            assert SECRET not in response.text
            assert "HUMAN_REVIEW" not in response.text
            assert not path.exists()
    finally:
        _clear()


def test_wildcard_listener_disables_login_when_configured_host_is_loopback(tmp_path):
    repository = _repository(tmp_path)
    settings = _settings(tmp_path)
    assert settings.host == "127.0.0.1"
    app.dependency_overrides[get_settings] = lambda: settings
    app.state.human_session_repository = repository
    exposed = TestClient(app, base_url="http://0.0.0.0")
    loopback = TestClient(app, base_url="http://127.0.0.1")
    try:
        spoofed = exposed.get(
            "/review-login",
            headers={"host": "127.0.0.1", "x-forwarded-for": "127.0.0.1"},
        )
        queue = exposed.get("/review-cases", headers={"host": "127.0.0.1"})
        posted = exposed.post(
            "/review-login",
            content=f"developmentSecret={SECRET}".encode("utf-8"),
            headers={
                "content-type": "application/x-www-form-urlencoded",
                "origin": "http://0.0.0.0",
                "host": "127.0.0.1",
            },
            follow_redirects=False,
        )
        shown = loopback.get("/review-login")
        assert spoofed.status_code == posted.status_code == 404
        assert "<form" not in spoofed.text
        assert queue.status_code == 503
        assert "This demo is not available." in queue.text
        assert "set-cookie" not in {name.lower() for name in posted.headers}
        assert shown.status_code == 200
        assert 'name="developmentSecret"' in shown.text
        assert _rows(repository) == []
    finally:
        _clear()


def test_https_cookie_is_secure_and_return_url_is_ignored(tmp_path):
    repository = _repository(tmp_path)
    _bind(_settings(tmp_path), repository)
    client = TestClient(app, base_url="https://127.0.0.1")
    try:
        posted = client.post(
            "/review-login?next=https://evil.example/phish",
            content=f"developmentSecret={SECRET}".encode("utf-8"),
            headers={
                "content-type": "application/x-www-form-urlencoded",
                "origin": "https://127.0.0.1",
                "x-forwarded-proto": "http",
            },
            follow_redirects=False,
        )
        assert posted.status_code == 303
        assert posted.headers["location"] == "/review-cases"
        assert "secure" in posted.headers["set-cookie"].lower()
    finally:
        _clear()


def test_login_rejects_bad_origin_and_malformed_or_oversized_bodies(tmp_path):
    repository = _repository(tmp_path)
    client = _bind(_settings(tmp_path), repository)
    try:
        bad_origin = _login(client, headers={"origin": "http://evil.example"})
        oversized = _login(client, content=b"developmentSecret=" + b"a" * 1100)
        extra = _login(client, content=b"developmentSecret=" + SECRET.encode() + b"&principalId=other")
        missing = _login(client, content=b"")
        assert bad_origin.status_code == 400
        assert oversized.status_code == 400
        assert extra.status_code == 400
        assert missing.status_code == 400
        assert _rows(repository) == []
        assert SECRET not in oversized.text
    finally:
        _clear()


def test_logout_revokes_only_that_browser_session(tmp_path):
    repository = _repository(tmp_path)
    clock = Clock(NOW)
    _bind(_settings(tmp_path), repository, clock)
    first = TestClient(app, base_url="http://127.0.0.1")
    second = TestClient(app, base_url="http://127.0.0.1")
    try:
        left = _login(first)
        right = _login(second)
        left_token = _cookie(left)
        right_token = _cookie(right)
        service = HumanSessionService(repository, clock=clock)
        logged_out = first.post("/review-logout", headers=ORIGIN, follow_redirects=False)
        assert logged_out.status_code == 303
        assert logged_out.headers["location"] == "/review-login"
        assert "max-age=0" in logged_out.headers["set-cookie"].lower()
        with pytest.raises(HumanSessionRejected):
            service.resolve(left_token)
        assert service.resolve(right_token).principal_id == "lab-reviewer"
        first.cookies.set(SESSION_COOKIE, left_token)
        again = first.post("/review-logout", headers=ORIGIN, follow_redirects=False)
        assert again.status_code == 303
        assert service.resolve(right_token).session_id
    finally:
        _clear()


def test_absolute_expiry_and_invalid_cookie_do_not_resolve(tmp_path):
    repository = _repository(tmp_path)
    clock = Clock(NOW)
    client = _bind(_settings(tmp_path), repository, clock)
    try:
        posted = _login(client)
        token = _cookie(posted)
        service = HumanSessionService(repository, clock=clock)
        clock.moment = NOW + timedelta(seconds=SESSION_TTL_SECONDS)
        with pytest.raises(HumanSessionRejected):
            service.resolve(token)
        client.cookies.set(SESSION_COOKIE, token)
        expired = client.post("/review-logout", headers=ORIGIN, follow_redirects=False)
        client.cookies.set(SESSION_COOKIE, "not-a-token")
        malformed = client.post("/review-logout", headers=ORIGIN, follow_redirects=False)
        assert expired.status_code == 303
        assert malformed.status_code == 303
        assert token not in expired.text
    finally:
        _clear()


def test_logout_origin_and_body_do_not_revoke(tmp_path):
    repository = _repository(tmp_path)
    clock = Clock(NOW)
    client = _bind(_settings(tmp_path), repository, clock)
    try:
        token = _cookie(_login(client))
        service = HumanSessionService(repository, clock=clock)
        client.cookies.set(SESSION_COOKIE, token)
        foreign = client.post(
            "/review-logout",
            headers={"origin": "http://evil.example"},
            follow_redirects=False,
        )
        bodied = client.post(
            "/review-logout",
            content=b"developmentSecret=nope",
            headers={**ORIGIN, "content-type": "application/x-www-form-urlencoded"},
            follow_redirects=False,
        )
        assert foreign.status_code == 400
        assert bodied.status_code == 400
        assert service.resolve(token).principal_id == "lab-reviewer"
        missing = client.get("/review-logout")
        assert missing.status_code == 405
    finally:
        _clear()


def test_missing_or_unavailable_session_store_fails_closed(tmp_path):
    garbage = tmp_path / "garbage.sqlite3"
    garbage.write_bytes(b"not a database")
    client = _bind(_settings(tmp_path, human_session_db_path=str(garbage)))
    try:
        unavailable = _login(client)
        assert unavailable.status_code == 503
        assert "not available" in unavailable.text
        assert str(garbage) not in unavailable.text
        assert "Traceback" not in unavailable.text
        assert SECRET not in unavailable.text
        assert "set-cookie" not in {name.lower() for name in unavailable.headers}
    finally:
        _clear()

    repository = _repository(tmp_path)
    posted = None

    class BrokenRepository:
        def insert(self, session, *, now: str) -> None:
            raise HumanSessionUnavailable

        def get_by_token_hash(self, token_hash: str, *, now: str):
            return repository.get_by_token_hash(token_hash, now=now)

        def revoke(self, token_hash: str, *, revoked_at: str, now: str) -> None:
            raise HumanSessionUnavailable

    client = _bind(_settings(tmp_path), BrokenRepository())
    try:
        denied = _login(client)
        assert denied.status_code == 503
        assert _rows(repository) == []
    finally:
        _clear()


def test_session_cookie_does_not_authorize_internal_routes(tmp_path):
    repository = _repository(tmp_path)
    client = _bind(_settings(tmp_path), repository)
    try:
        token = _cookie(_login(client))
        client.cookies.set(SESSION_COOKIE, token)
        health = client.get("/health")
        internal = client.post("/internal/agent/follow-up", headers=ORIGIN)
        assert health.status_code == 200
        assert health.json() == {"status": "ok"}
        assert internal.status_code == 401
        source = Path(review_cases.__code__.co_filename).read_text(encoding="utf-8")
        assert "render_review_queue" in source
        assert "development_authenticator" not in source.split("def review_cases")[1].split("def ")[0]
    finally:
        _clear()


def test_login_module_does_not_import_review_or_model_code():
    source = Path(__file__).resolve().parents[1].joinpath("app", "human_development_auth.py").read_text(
        encoding="utf-8"
    ).lower()
    for token in ("gemini", "langgraph", "followup_review", "followup_coordination", "fhir", "httpx"):
        assert token not in source
    assert "compare_digest" in source
