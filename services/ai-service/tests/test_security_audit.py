"""Durable security audit foundation. It does not start external services."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.human_development_auth import SESSION_COOKIE
from app.main import app, get_settings
from app.security_audit import (
    SecurityAuditEvent,
    SecurityAuditRejected,
    SecurityAuditUnavailable,
    authentication_event,
    reject_untrusted_metadata,
    validate_security_audit_event,
)
from app.security_audit_sqlite import (
    SQLiteSecurityAuditRepository,
    SecurityAuditStoreInitializationError,
    audit_database_path,
)
from app.human_session_sqlite import SQLiteHumanSessionRepository


SECRET = "development-secret-value-32chars-min"
SERVICE_TOKEN = "synthetic-service-token-a"
SIGNING_SECRET = "synthetic-form-signing-secret-b"
NOW = datetime(2026, 10, 23, 16, 0, tzinfo=timezone.utc)


class Clock:
    def __call__(self) -> datetime:
        return NOW


def _settings(tmp_path: Path) -> Settings:
    return Settings(
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
        security_audit_db_path=str(tmp_path / "security-audit.sqlite3"),
    )


def _client(settings: Settings) -> TestClient:
    app.dependency_overrides[get_settings] = lambda: settings
    app.state.human_session_clock = Clock()
    return TestClient(app, base_url="http://127.0.0.1")


def _clear() -> None:
    app.dependency_overrides.clear()
    for name in ("human_session_repository", "human_session_clock", "security_audit_repository"):
        if hasattr(app.state, name):
            delattr(app.state, name)


def _post(client: TestClient, secret: str):
    return client.post(
        "/review-login",
        content=f"developmentSecret={secret}",
        headers={"content-type": "application/x-www-form-urlencoded", "origin": "http://127.0.0.1"},
        follow_redirects=False,
    )


def test_event_is_durable_across_repository_restart(tmp_path: Path):
    path = tmp_path / "security-audit.sqlite3"
    first = SQLiteSecurityAuditRepository(path)
    first.initialize()
    stored = first.append(
        authentication_event(
            outcome="allowed",
            actor_id="lab-reviewer",
            actor_type="development_principal",
            reason_code="credential_accepted",
            clock=Clock(),
        )
    )
    second = SQLiteSecurityAuditRepository(path)
    second.initialize()
    loaded = second.get(stored.event_id)
    assert loaded == stored
    assert second.list_by_correlation(stored.correlation_id) == (stored,)
    raw = path.read_bytes()
    assert SECRET.encode() not in raw
    assert SERVICE_TOKEN.encode() not in raw


def test_login_records_allowed_and_denied_without_the_secret(tmp_path: Path):
    settings = _settings(tmp_path)
    client = _client(settings)
    try:
        denied = _post(client, "wrong-secret-value-which-is-long-enough")
        allowed = _post(client, SECRET)
    finally:
        _clear()
    assert denied.status_code == 401
    assert SESSION_COOKIE not in denied.cookies
    assert allowed.status_code == 303
    assert allowed.headers["location"] == "/review-cases"
    repository = SQLiteSecurityAuditRepository(tmp_path / "security-audit.sqlite3")
    repository.initialize()
    with repository._scope() as connection:
        rows = [
            tuple(row)
            for row in connection.execute(
                """
                SELECT event_type, actor_type, actor_id, organization_id, source_service,
                       resource_type, resource_reference, action, outcome, reason_code,
                       metadata_json, contract_version
                FROM security_audit_events
                ORDER BY rowid
                """
            ).fetchall()
        ]
    assert rows == [
        (
            "authentication",
            "anonymous",
            "anonymous",
            None,
            "ai-service",
            "authentication",
            "development-login",
            "authenticate",
            "denied",
            "credential_rejected",
            '{"route":"/review-login"}',
            "security-audit-v1",
        ),
        (
            "authentication",
            "development_principal",
            "lab-reviewer",
            None,
            "ai-service",
            "authentication",
            "development-login",
            "authenticate",
            "allowed",
            "credential_accepted",
            '{"route":"/review-login"}',
            "security-audit-v1",
        ),
    ]
    raw = (tmp_path / "security-audit.sqlite3").read_bytes()
    assert SECRET.encode() not in raw
    assert b"wrong-secret" not in raw


def test_field_and_metadata_rejection():
    event = authentication_event(
        outcome="denied",
        actor_id="anonymous",
        actor_type="anonymous",
        reason_code="credential_rejected",
        clock=Clock(),
    )
    with_token = SecurityAuditEvent(
        event_id=event.event_id,
        timestamp_utc=event.timestamp_utc,
        event_type=event.event_type,
        actor_type=event.actor_type,
        actor_id=event.actor_id,
        organization_id=None,
        source_service=event.source_service,
        resource_type=event.resource_type,
        resource_reference=event.resource_reference,
        action=event.action,
        outcome=event.outcome,
        reason_code=event.reason_code,
        correlation_id=event.correlation_id,
        metadata=(("x-service-token", SECRET),),
    )
    try:
        validate_security_audit_event(with_token)
        raise AssertionError("sensitive metadata was accepted")
    except SecurityAuditRejected:
        pass
    try:
        reject_untrusted_metadata(
            {
                "route": "bearer secret",
                "password": "hidden",
                "note": '{"resourceType":"Patient","name":"synthetic"}',
            }
        )
        raise AssertionError("unexpected metadata was accepted")
    except SecurityAuditRejected:
        pass
    try:
        validate_security_audit_event(
            SecurityAuditEvent(
                **{**event.__dict__, "outcome": "approved", "metadata": event.metadata}
            )
        )
        raise AssertionError("unexpected outcome was accepted")
    except SecurityAuditRejected:
        pass


def test_repository_has_no_public_mutation_methods():
    public = {name for name in dir(SQLiteSecurityAuditRepository) if not name.startswith("_")}
    assert {"append", "get", "initialize", "list_by_correlation"} <= public
    assert public.isdisjoint({"update", "delete", "remove", "purge"})
    root = Path(__file__).parents[1] / "app"
    sql = (root / "migrations" / "002_security_audit.sql").read_text(encoding="utf-8")
    module = (root / "security_audit_sqlite.py").read_text(encoding="utf-8")
    assert "UPDATE" not in sql and "DELETE" not in sql
    assert "UPDATE " not in module and "DELETE " not in module


def test_placeholder_session_path_does_not_write_beside_the_working_directory(tmp_path: Path):
    session = SQLiteHumanSessionRepository(tmp_path / "nested" / "human-session.sqlite3")
    session.initialize()

    class Placeholder:
        security_audit_db_path = ""
        human_session_db_path = "unused-human-session-overridden-by-state.sqlite3"

    class Wrapped:
        def __init__(self, inner: SQLiteHumanSessionRepository) -> None:
            self.inner = inner

    resolved = Path(audit_database_path(Placeholder(), session_repository=Wrapped(session)))
    assert resolved == (tmp_path / "nested" / "security-audit.sqlite3").resolve()
    assert not Path("security-audit.sqlite3").exists()
    try:
        audit_database_path(Placeholder())
        raise AssertionError("bare session path selected a database")
    except SecurityAuditStoreInitializationError:
        pass


def test_audit_persistence_failure_does_not_issue_a_session(tmp_path: Path):
    class Down:
        def append(self, event: SecurityAuditEvent) -> SecurityAuditEvent:
            raise SecurityAuditUnavailable("disk full")

    settings = _settings(tmp_path)
    client = _client(settings)
    app.state.security_audit_repository = Down()
    try:
        allowed = _post(client, SECRET)
        denied = _post(client, "wrong-secret-value-which-is-long-enough")
    finally:
        _clear()
    assert allowed.status_code == 503
    assert SESSION_COOKIE not in allowed.cookies
    assert denied.status_code == 503
    assert b"disk full" not in allowed.content
    assert SECRET.encode() not in allowed.content
