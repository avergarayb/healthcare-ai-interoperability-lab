"""Application session domain for a future human review login.

This module stores and resolves opaque sessions. It does not serve HTTP,
authenticate a development secret, or decide review or coordination policy.
"""

from __future__ import annotations

import hashlib
import re
import secrets
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol


DEVELOPMENT_AUTHENTICATOR_V1 = "DEVELOPMENT_AUTHENTICATOR_V1"
SESSION_TTL_SECONDS = 28_800
SESSION_CLEANUP_GRACE_SECONDS = 86_400
_TOKEN = re.compile(r"^[A-Za-z0-9_-]{43}$")
_TOKEN_HASH = re.compile(r"^[0-9a-f]{64}$")
_PRINCIPAL_ID = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")
_UTC_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$")


class HumanSessionRejected(Exception):
    """The presented token does not identify a live session."""


class HumanSessionUnavailable(Exception):
    """The session store cannot complete the operation."""


class HumanSessionStoreInitializationError(RuntimeError):
    """The session store cannot be opened safely."""


@dataclass(frozen=True)
class HumanPrincipal:
    principal_id: str
    display_name: str
    authenticator_id: str


@dataclass(frozen=True)
class HumanSession:
    session_id: str
    token_hash: str
    principal_id: str
    display_name: str
    authenticator_id: str
    issued_at: str
    expires_at: str
    revoked_at: str | None


@dataclass(frozen=True)
class IssuedHumanSession:
    """Raw token plus the stored record. The token exists only in this object."""

    session: HumanSession
    token: str


class HumanSessionRepository(Protocol):
    def insert(self, session: HumanSession, *, now: str) -> None: ...

    def get_by_token_hash(self, token_hash: str, *, now: str) -> HumanSession | None: ...

    def revoke(self, token_hash: str, *, revoked_at: str, now: str) -> None: ...


class HumanSessionService:
    """Issue, resolve and revoke opaque sessions. No operational policy."""

    def __init__(
        self,
        repository: HumanSessionRepository,
        *,
        clock: Callable[[], datetime],
        token_factory: Callable[[], str] = lambda: secrets.token_urlsafe(32),
        id_factory: Callable[[], uuid.UUID] = uuid.uuid4,
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._token_factory = token_factory
        self._id_factory = id_factory

    def issue(self, principal: HumanPrincipal) -> IssuedHumanSession:
        validate_human_principal(principal)
        moment = _require_aware(self._clock())
        issued_at = _format_timestamp(moment)
        expires_at = _format_timestamp(moment + timedelta(seconds=SESSION_TTL_SECONDS))
        token = self._token_factory()
        token_hash = hash_session_token(token)
        session_id = _session_id(self._id_factory())
        session = HumanSession(
            session_id=session_id,
            token_hash=token_hash,
            principal_id=principal.principal_id,
            display_name=principal.display_name,
            authenticator_id=principal.authenticator_id,
            issued_at=issued_at,
            expires_at=expires_at,
            revoked_at=None,
        )
        validate_human_session(session)
        try:
            self._repository.insert(session, now=issued_at)
        except HumanSessionUnavailable:
            raise
        except (OSError, ValueError) as exc:
            raise HumanSessionUnavailable from exc
        return IssuedHumanSession(session=session, token=token)

    def resolve(self, token: str) -> HumanSession:
        token_hash = hash_session_token(token)
        now = _format_timestamp(_require_aware(self._clock()))
        try:
            session = self._repository.get_by_token_hash(token_hash, now=now)
        except HumanSessionUnavailable:
            raise
        except (OSError, ValueError) as exc:
            raise HumanSessionUnavailable from exc
        if session is None or not _is_live(session, now):
            raise HumanSessionRejected
        return session

    def revoke(self, token: str) -> None:
        token_hash = hash_session_token(token)
        now = _format_timestamp(_require_aware(self._clock()))
        try:
            self._repository.revoke(token_hash, revoked_at=now, now=now)
        except HumanSessionUnavailable:
            raise
        except (OSError, ValueError) as exc:
            raise HumanSessionUnavailable from exc


def validate_human_principal(principal: HumanPrincipal) -> HumanPrincipal:
    if not isinstance(principal.principal_id, str) or _PRINCIPAL_ID.fullmatch(principal.principal_id) is None:
        raise ValueError("human principal id is invalid")
    if not isinstance(principal.display_name, str) or not _valid_display_name(principal.display_name):
        raise ValueError("human principal display name is invalid")
    if principal.authenticator_id != DEVELOPMENT_AUTHENTICATOR_V1:
        raise ValueError("human authenticator id is invalid")
    return principal


def validate_human_session(session: HumanSession) -> HumanSession:
    _session_id_value(session.session_id)
    if not isinstance(session.token_hash, str) or _TOKEN_HASH.fullmatch(session.token_hash) is None:
        raise ValueError("human session token hash is invalid")
    validate_human_principal(
        HumanPrincipal(
            principal_id=session.principal_id,
            display_name=session.display_name,
            authenticator_id=session.authenticator_id,
        )
    )
    issued_at = _parse_timestamp(session.issued_at)
    expires_at = _parse_timestamp(session.expires_at)
    if expires_at - issued_at != timedelta(seconds=SESSION_TTL_SECONDS):
        raise ValueError("human session lifetime is invalid")
    if session.revoked_at is not None:
        revoked_at = _parse_timestamp(session.revoked_at)
        if revoked_at < issued_at:
            raise ValueError("human session revocation is invalid")
    return session


def session_cleanup_cutoff(now: str) -> str:
    return _format_timestamp(
        _parse_timestamp(now) - timedelta(seconds=SESSION_CLEANUP_GRACE_SECONDS)
    )


def hash_session_token(token: str) -> str:
    if not isinstance(token, str) or _TOKEN.fullmatch(token) is None:
        raise HumanSessionRejected
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _is_live(session: HumanSession, now: str) -> bool:
    if session.revoked_at is not None:
        return False
    return _parse_timestamp(now) < _parse_timestamp(session.expires_at)


def _valid_display_name(value: str) -> bool:
    if not 1 <= len(value) <= 80:
        return False
    return all(ord(character) >= 32 and ord(character) != 127 for character in value)


def _session_id(value: uuid.UUID) -> str:
    if value.version != 4:
        raise HumanSessionUnavailable
    return str(value)


def _session_id_value(value: str) -> str:
    try:
        parsed = uuid.UUID(value)
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("human session id is invalid") from exc
    if parsed.version != 4 or str(parsed) != value:
        raise ValueError("human session id is invalid")
    return value


def _require_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise HumanSessionUnavailable
    return value.astimezone(timezone.utc)


def _format_timestamp(value: datetime) -> str:
    moment = _require_aware(value)
    return moment.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _parse_timestamp(value: str) -> datetime:
    if not isinstance(value, str) or _UTC_TIMESTAMP.fullmatch(value) is None:
        raise ValueError("human session timestamp is invalid")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise ValueError("human session timestamp is invalid") from exc
