from __future__ import annotations

import base64
import hashlib
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.followup_review_sqlite import SCHEMA_VERSION as REVIEW_SCHEMA_VERSION
from app.human_session import (
    DEVELOPMENT_AUTHENTICATOR_V1,
    SESSION_CLEANUP_GRACE_SECONDS,
    SESSION_TTL_SECONDS,
    HumanPrincipal,
    HumanSessionRejected,
    HumanSessionService,
    HumanSessionStoreInitializationError,
    HumanSessionUnavailable,
    hash_session_token,
)
from app.human_session_sqlite import SCHEMA_VERSION, SQLiteHumanSessionRepository, _MIGRATION


NOW = datetime(2026, 10, 7, 15, 0, tzinfo=timezone.utc)
PRINCIPAL = HumanPrincipal(
    principal_id="lab-reviewer",
    display_name="Lab reviewer",
    authenticator_id=DEVELOPMENT_AUTHENTICATOR_V1,
)
REVIEW_MIGRATION_001 = "94a043adffad718fd0fcdc79794cd044d19e2471db89da664170ceb33416be80"
APP = Path(__file__).resolve().parents[1] / "app"
APPROVED_COLUMNS = {
    "session_id",
    "token_hash",
    "principal_id",
    "display_name",
    "authenticator_id",
    "issued_at",
    "expires_at",
    "revoked_at",
}


class Clock:
    def __init__(self, moment: datetime) -> None:
        self.moment = moment

    def __call__(self) -> datetime:
        return self.moment


def _ready(tmp_path: Path, clock: Clock | None = None):
    clock = clock or Clock(NOW)
    repository = SQLiteHumanSessionRepository(tmp_path / "human-session.sqlite3")
    repository.initialize()
    return repository, HumanSessionService(repository, clock=clock), clock


def _rows(repository: SQLiteHumanSessionRepository) -> list[sqlite3.Row]:
    with sqlite3.connect(repository.database_path) as connection:
        connection.row_factory = sqlite3.Row
        return list(connection.execute("SELECT * FROM human_sessions").fetchall())


def _token_bytes(token: str) -> bytes:
    padding = "=" * (-len(token) % 4)
    return base64.urlsafe_b64decode(token + padding)


def test_token_has_256_bits_and_only_its_hash_is_stored(tmp_path):
    repository, service, _clock = _ready(tmp_path)
    issued = service.issue(PRINCIPAL)
    assert len(_token_bytes(issued.token)) == 32
    assert issued.token not in {
        issued.session.session_id,
        issued.session.token_hash,
        issued.session.principal_id,
        issued.session.display_name,
    }
    assert issued.session.token_hash == hash_session_token(issued.token)
    assert issued.session.token_hash == hashlib.sha256(issued.token.encode("utf-8")).hexdigest()
    for candidate in repository.database_path.parent.glob(repository.database_path.name + "*"):
        assert issued.token.encode("utf-8") not in candidate.read_bytes()
    stored = _rows(repository)
    assert len(stored) == 1
    assert set(stored[0].keys()) == APPROVED_COLUMNS
    assert stored[0]["token_hash"] == issued.session.token_hash
    assert "patient" not in APPROVED_COLUMNS
    assert "fhir" not in " ".join(APPROVED_COLUMNS)


def test_two_sessions_for_one_principal_have_independent_identifiers(tmp_path):
    _repository, service, _clock = _ready(tmp_path)
    first = service.issue(PRINCIPAL)
    second = service.issue(PRINCIPAL)
    assert first.session.session_id != second.session.session_id
    assert first.token != second.token
    assert first.session.token_hash != second.session.token_hash
    assert service.resolve(first.token).session_id == first.session.session_id
    assert service.resolve(second.token).session_id == second.session.session_id


def test_resolve_accepts_a_live_session_without_extending_it(tmp_path):
    repository, service, clock = _ready(tmp_path)
    issued = service.issue(PRINCIPAL)
    original_expiry = issued.session.expires_at
    clock.moment = NOW + timedelta(seconds=SESSION_TTL_SECONDS) - timedelta(microseconds=1)
    resolved = service.resolve(issued.token)
    assert resolved.expires_at == original_expiry
    assert resolved.revoked_at is None
    assert _rows(repository)[0]["expires_at"] == original_expiry


def test_absolute_expiry_rejects_without_renewal(tmp_path):
    repository, service, clock = _ready(tmp_path)
    issued = service.issue(PRINCIPAL)
    clock.moment = NOW + timedelta(seconds=SESSION_TTL_SECONDS)
    with pytest.raises(HumanSessionRejected):
        service.resolve(issued.token)
    row = _rows(repository)[0]
    assert row["expires_at"] == issued.session.expires_at
    assert row["revoked_at"] is None


def test_revoke_invalidates_only_the_selected_session(tmp_path):
    repository, service, clock = _ready(tmp_path)
    first = service.issue(PRINCIPAL)
    second = service.issue(PRINCIPAL)
    service.revoke(first.token)
    with pytest.raises(HumanSessionRejected):
        service.resolve(first.token)
    assert service.resolve(second.token).session_id == second.session.session_id
    service.revoke(first.token)
    rows = {row["session_id"]: row for row in _rows(repository)}
    assert rows[first.session.session_id]["revoked_at"] == "2026-10-07T15:00:00.000000Z"
    assert rows[second.session.session_id]["revoked_at"] is None
    clock.moment = NOW + timedelta(minutes=5)
    service.revoke(first.token)
    revoked = next(row for row in _rows(repository) if row["session_id"] == first.session.session_id)
    assert revoked["revoked_at"] == "2026-10-07T15:00:00.000000Z"


def test_unknown_and_malformed_tokens_are_rejected(tmp_path):
    repository, service, _clock = _ready(tmp_path)
    unknown = service.issue(PRINCIPAL).token
    service.revoke(unknown)
    replacement = service.issue(PRINCIPAL)
    with pytest.raises(HumanSessionRejected):
        service.resolve(replacement.token[:-1] + ("A" if replacement.token[-1] != "A" else "B"))
    repository.database_path.unlink()
    with pytest.raises(HumanSessionRejected):
        service.resolve("short")
    with pytest.raises(HumanSessionRejected):
        service.revoke("bad token")


def test_cleanup_removes_sessions_expired_more_than_24_hours(tmp_path):
    repository, service, clock = _ready(tmp_path)
    issued = service.issue(PRINCIPAL)
    clock.moment = NOW + timedelta(seconds=SESSION_TTL_SECONDS + SESSION_CLEANUP_GRACE_SECONDS)
    with pytest.raises(HumanSessionRejected):
        service.resolve(issued.token)
    assert len(_rows(repository)) == 1
    clock.moment = NOW + timedelta(
        seconds=SESSION_TTL_SECONDS + SESSION_CLEANUP_GRACE_SECONDS, microseconds=1
    )
    with pytest.raises(HumanSessionRejected):
        service.resolve(issued.token)
    assert _rows(repository) == []


def test_restart_keeps_an_unexpired_session(tmp_path):
    repository, service, _clock = _ready(tmp_path)
    issued = service.issue(PRINCIPAL)
    restarted = SQLiteHumanSessionRepository(repository.database_path)
    restarted.initialize()
    resolved = HumanSessionService(restarted, clock=Clock(NOW)).resolve(issued.token)
    assert resolved.session_id == issued.session.session_id
    assert resolved.token_hash == issued.session.token_hash


def test_schema_initializes_once_and_rejects_a_future_version(tmp_path):
    path = tmp_path / "nested" / "human-session.sqlite3"
    repository = SQLiteHumanSessionRepository(path)
    repository.initialize()
    repository.initialize()
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert connection.execute("PRAGMA index_list(human_sessions)").fetchall()
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA user_version = 2")
    with pytest.raises(HumanSessionStoreInitializationError):
        SQLiteHumanSessionRepository(path).initialize()
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 2


def test_corrupt_schema_and_garbage_file_fail_closed(tmp_path):
    path = tmp_path / "human-session.sqlite3"
    repository = SQLiteHumanSessionRepository(path)
    repository.initialize()
    with sqlite3.connect(path) as connection:
        connection.execute("DROP TABLE human_sessions")
    with pytest.raises(HumanSessionStoreInitializationError):
        SQLiteHumanSessionRepository(path).initialize()
    garbage = tmp_path / "garbage.sqlite3"
    garbage.write_bytes(b"not a database")
    with pytest.raises(HumanSessionStoreInitializationError):
        SQLiteHumanSessionRepository(garbage).initialize()
    with pytest.raises(HumanSessionStoreInitializationError):
        SQLiteHumanSessionRepository(":memory:")


def test_failed_migration_rolls_back(tmp_path, monkeypatch):
    path = tmp_path / "partial.sqlite3"
    migration = tmp_path / "broken.sql"
    migration.write_text(
        "BEGIN IMMEDIATE; CREATE TABLE should_rollback(id TEXT); INVALID SQL; COMMIT;",
        encoding="utf-8",
    )
    monkeypatch.setattr("app.human_session_sqlite._MIGRATION", migration)
    with pytest.raises(HumanSessionStoreInitializationError):
        SQLiteHumanSessionRepository(path).initialize()
    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT name FROM sqlite_master WHERE name='should_rollback'"
        ).fetchone() is None
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 0


def test_sqlite_errors_fail_closed_and_duplicate_hash_is_rejected(tmp_path, monkeypatch):
    repository, service, _clock = _ready(tmp_path)
    issued = service.issue(PRINCIPAL)
    with pytest.raises(HumanSessionUnavailable):
        repository.insert(issued.session, now=issued.session.issued_at)
    assert len(_rows(repository)) == 1

    def fail(self):
        raise sqlite3.OperationalError("disk full")

    monkeypatch.setattr(SQLiteHumanSessionRepository, "_connect", fail)
    with pytest.raises(HumanSessionUnavailable):
        service.resolve(issued.token)
    with pytest.raises(HumanSessionUnavailable):
        service.issue(PRINCIPAL)


def test_store_is_required_before_a_well_formed_unknown_token(tmp_path):
    repository = SQLiteHumanSessionRepository(tmp_path / "human-session.sqlite3")
    service = HumanSessionService(repository, clock=Clock(NOW))
    with pytest.raises(HumanSessionUnavailable):
        service.issue(PRINCIPAL)
    repository.initialize()
    issued = service.issue(PRINCIPAL)
    repository.database_path.unlink()
    for suffix in ("-wal", "-shm"):
        sidecar = Path(str(repository.database_path) + suffix)
        if sidecar.exists():
            sidecar.unlink()
    with pytest.raises(HumanSessionUnavailable):
        service.resolve(issued.token)


def test_invalid_principal_is_not_stored(tmp_path):
    repository, service, _clock = _ready(tmp_path)
    rejected = HumanPrincipal("Lab Reviewer", "Lab reviewer", DEVELOPMENT_AUTHENTICATOR_V1)
    with pytest.raises(ValueError):
        service.issue(rejected)
    with pytest.raises(ValueError):
        service.issue(
            HumanPrincipal("lab-reviewer", "Lab reviewer", "OIDC_AUTHENTICATOR_V1")
        )
    with pytest.raises(ValueError):
        service.issue(HumanPrincipal("lab-reviewer", "Lab\nreviewer", DEVELOPMENT_AUTHENTICATOR_V1))
    assert _rows(repository) == []


def test_concurrent_resolution_and_revocation(tmp_path):
    _repository, service, _clock = _ready(tmp_path)
    live = service.issue(PRINCIPAL)
    closing = service.issue(PRINCIPAL)

    def resolve_live() -> str:
        return service.resolve(live.token).session_id

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert set(pool.map(lambda _index: resolve_live(), range(8))) == {live.session.session_id}
        list(pool.map(lambda _index: service.revoke(closing.token), range(8)))
    with pytest.raises(HumanSessionRejected):
        service.resolve(closing.token)
    assert service.resolve(live.token).session_id == live.session.session_id


def test_review_migrations_and_http_routes_stay_untouched():
    assert REVIEW_SCHEMA_VERSION == 2
    review_migration = (APP / "migrations" / "001_follow_up_review.sql").read_bytes()
    coordination_migration = (APP / "migrations" / "002_follow_up_coordination_request.sql").read_text(
        encoding="utf-8"
    )
    session_migration = _MIGRATION.read_text(encoding="utf-8")
    assert hashlib.sha256(review_migration).hexdigest() == REVIEW_MIGRATION_001
    assert "human_sessions" not in coordination_migration
    assert "follow_up_review_cases" not in session_migration
    assert "user_version = 1" in session_migration
    main = (APP / "main.py").read_text(encoding="utf-8")
    client = (APP / "human_review_client.py").read_text(encoding="utf-8")
    assert "human_session" not in main
    assert "from app.human_development_auth import require_human_session" in client
    assert "from app.human_session" not in client


def test_session_modules_do_not_import_operational_or_model_code():
    source = "\n".join(
        (APP / name).read_text(encoding="utf-8")
        for name in ("human_session.py", "human_session_sqlite.py")
    )
    lowered = source.lower()
    for token in (
        "gemini",
        "langgraph",
        "followup_review",
        "followup_coordination",
        "human_review_client",
        "fastapi",
        "httpx",
        "fhir",
        "import logging",
    ):
        assert token not in lowered
    assert "DEVELOPMENT_AUTHENTICATOR_V1" in source
