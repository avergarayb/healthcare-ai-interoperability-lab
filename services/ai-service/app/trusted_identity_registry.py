"""Opt-in workload policy store. JWT verification and business state are not owned here."""
from __future__ import annotations

import json
import re
import sqlite3
import uuid
from contextlib import closing, contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from app.oidc_config import AUDIENCE, ID, PERMISSION, Closed, Rejected, TrustConfig, unique_object

VERSION = "trusted-identity-registry-v1"
APPLICATION_ID = 0x49414D34
MIGRATION = Path(__file__).parent / "identity_registry_migrations/001_trusted_identity_registry.sql"
PERMISSION_ID = re.compile(r"[a-z][a-z0-9.-]{0,79}\Z")
OPERATIONS = frozenset({"enable-principal", "disable-principal", "enable-binding", "disable-binding",
                        "grant-membership", "revoke-membership", "grant-permission", "revoke-permission"})


class RegistryError(Exception):
    """Closed local codes only; never publish SQLite/fixture exception details."""


def identifier(value):
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise RegistryError("invalid_identifier")
    return value


class Principal(Closed):
    principal_id: str
    principal_type: Literal["workload"]
    enabled: bool


class Organization(Closed):
    organization_id: str
    enabled: bool


class Binding(Closed):
    binding_id: str
    issuer: str
    external_subject: str = Field(min_length=1, max_length=512)
    client_id: str = Field(pattern=r"^[A-Za-z0-9._-]{1,128}$")
    principal_id: str
    enabled: bool


class Membership(Closed):
    principal_id: str
    organization_id: str
    enabled: bool


class Grant(Membership):
    permission: str


class RegistryFixture(Closed):
    contract_version: Literal["trusted-identity-registry-v1"]
    provider_id: str
    issuer: str
    audience: Literal["healthcare-ai-api"]
    principals: tuple[Principal, ...] = Field(min_length=1, max_length=64)
    organizations: tuple[Organization, ...] = Field(min_length=1, max_length=32)
    bindings: tuple[Binding, ...] = Field(min_length=1, max_length=64)
    memberships: tuple[Membership, ...] = Field(max_length=2048)
    grants: tuple[Grant, ...] = Field(max_length=4096)

    @model_validator(mode="after")
    def coherent(self):
        identifier(self.provider_id)
        # Syntax only: no URL is ever fetched by the registry. Runtime trust remains in TrustConfig.
        if (not 1 <= len(self.issuer) <= 2048 or not self.issuer.startswith(("https://", "http://"))
                or any(ord(c) < 33 for c in self.issuer)):
            raise ValueError("invalid issuer")
        for row in (*self.principals, *self.organizations, *self.bindings, *self.memberships, *self.grants):
            for name in ("principal_id", "organization_id", "binding_id"):
                if hasattr(row, name):
                    identifier(getattr(row, name))
        if any(b.issuer != self.issuer or any(ord(c) < 33 for c in b.external_subject) for b in self.bindings):
            raise ValueError("invalid binding")
        if any(not PERMISSION_ID.fullmatch(g.permission) for g in self.grants):
            raise ValueError("invalid permission")
        return self


def load_fixture(path):
    try:
        with Path(path).open("rb") as stream:
            raw = stream.read(1048577)
        if len(raw) > 1048576:
            raise ValueError("fixture too large")
        value = json.loads(raw, object_pairs_hook=unique_object)
        return RegistryFixture.model_validate_json(json.dumps(value))
    except (ValueError, TypeError, OSError, RegistryError):
        raise RegistryError("invalid_fixture") from None


def timestamp():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def schema(connection):
    return connection.execute("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type,name").fetchall()


@lru_cache(maxsize=1)
def expected_schema():
    with closing(sqlite3.connect(":memory:")) as connection:
        connection.executescript(MIGRATION.read_text(encoding="utf-8"))
        return schema(connection)


def safe_path(value, *, exists=True):
    path = Path(value)
    if not value or not path.is_absolute() or path.name.endswith(("-wal", "-shm", "-journal")):
        raise RegistryError("explicit_absolute_database_required")
    # Refuse aliases/reparse points/hard links. Local OS owners remain trusted; this is not an OS sandbox.
    if any(p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction()) for p in (path, *path.parents)):
        raise RegistryError("unsafe_database_path")
    if exists and (not path.is_file() or path.stat().st_nlink != 1):
        raise RegistryError("registry_missing_or_unsafe")
    return path


@dataclass(frozen=True)
class ResolvedPolicy:
    principal_id: str
    organization_id: str
    permissions: tuple[str, ...]
    revision: int


class TrustedIdentityRegistry:
    def __init__(self, path, forbidden_paths=()):
        self.path = safe_path(path, exists=False)
        if self.path.resolve() in {Path(p).resolve() for p in forbidden_paths if p}:
            raise RegistryError("separate_registry_required")

    @contextmanager
    def connection(self, *, write=False):
        connection = None
        try:
            path = safe_path(str(self.path))
            # rw/ro do not create an absent database. All requests open a fresh snapshot.
            connection = sqlite3.connect(path.as_uri() + ("?mode=rw" if write else "?mode=ro"), uri=True, timeout=1)
            connection.execute("PRAGMA trusted_schema=OFF")
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=1000")
            if not write:
                connection.execute("PRAGMA query_only=ON")
            connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            self.validate(connection)
            yield connection
            if write:
                connection.commit()
        except (OSError, ValueError, TypeError, sqlite3.Error):
            raise RegistryError("registry_unavailable") from None
        finally:
            if connection is not None:
                connection.rollback()
                connection.close()

    @staticmethod
    def validate(connection):
        if (connection.execute("PRAGMA user_version").fetchone()[0] != 1
                or connection.execute("PRAGMA application_id").fetchone()[0] != APPLICATION_ID
                or connection.execute("PRAGMA journal_mode").fetchone()[0].lower() != "wal"
                or schema(connection) != expected_schema()
                or connection.execute("PRAGMA quick_check").fetchone()[0] != "ok"
                or connection.execute("PRAGMA foreign_key_check").fetchone() is not None):
            raise RegistryError("incompatible_registry")
        metadata = connection.execute("SELECT contract_version,revision FROM registry_metadata WHERE singleton=1").fetchone()
        if metadata is None or metadata[0] != VERSION or metadata[1] < 1:
            raise RegistryError("incompatible_registry")
        audit = connection.execute("SELECT count(*),max(revision) FROM registry_policy_change_audit").fetchone()
        if audit != (metadata[1], metadata[1]):
            raise RegistryError("incompatible_change_audit")

    @staticmethod
    def append_change(connection, operation, target, organization, permission, enabled, operator):
        revision = connection.execute("SELECT revision FROM registry_metadata WHERE singleton=1").fetchone()[0]
        connection.execute("INSERT INTO registry_policy_change_audit VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (
            revision, str(uuid.uuid4()), "trusted-identity-registry-change-v1", timestamp(), operation,
            target, organization, permission, int(enabled), "local_operator_unverified", operator, 0))

    def initialize(self, fixture: RegistryFixture, operator=None):
        if operator is not None:
            identifier(operator)
        path = safe_path(str(self.path), exists=False)
        created = False
        try:
            # Validate before exclusive creation; never replace an existing file, including an empty one.
            fixture = RegistryFixture.model_validate_json(fixture.model_dump_json())
            with path.open("xb"):
                created = True
            with closing(sqlite3.connect(path, timeout=1)) as connection:
                connection.execute("PRAGMA foreign_keys=ON")
                if connection.execute("PRAGMA journal_mode=WAL").fetchone()[0].lower() != "wal":
                    raise RegistryError("wal_required")
                connection.execute("BEGIN IMMEDIATE")
                try:
                    for statement in MIGRATION.read_text(encoding="utf-8").split(";"):
                        if statement.strip():
                            connection.execute(statement)
                    connection.execute("PRAGMA user_version=1")
                    connection.execute(f"PRAGMA application_id={APPLICATION_ID}")
                    connection.execute("INSERT INTO registry_metadata VALUES (1,?,?,?,?,1)",
                                       (VERSION, fixture.provider_id, fixture.issuer, AUDIENCE))
                    now = timestamp()
                    connection.executemany("INSERT INTO registry_principal VALUES (?,?,?,1,?)",
                        [(p.principal_id, p.principal_type, int(p.enabled), now) for p in fixture.principals])
                    connection.executemany("INSERT INTO registry_organization VALUES (?,?)",
                        [(o.organization_id, int(o.enabled)) for o in fixture.organizations])
                    connection.executemany("INSERT INTO registry_binding VALUES (?,?,?,?,?,?,1,?)",
                        [(b.binding_id, b.issuer, b.external_subject, b.client_id, b.principal_id, int(b.enabled), now) for b in fixture.bindings])
                    connection.executemany("INSERT INTO registry_membership VALUES (?,?,?,1,?)",
                        [(m.principal_id, m.organization_id, int(m.enabled), now) for m in fixture.memberships])
                    connection.executemany("INSERT INTO registry_permission VALUES (?,?,?,?,1,?)",
                        [(g.principal_id, g.organization_id, g.permission, int(g.enabled), now) for g in fixture.grants])
                    self.append_change(connection, "init", "registry", None, None, True, operator)
                    self.validate(connection)
                    connection.commit()
                except BaseException:
                    connection.rollback()
                    raise
        except FileExistsError:
            raise RegistryError("registry_already_exists") from None
        except (OSError, ValueError, TypeError, sqlite3.Error):
            # An exclusively created empty file is retained on failure; never delete/reuse a target implicitly.
            raise RegistryError("registry_initialization_failed" if created else "registry_creation_failed") from None

    def resolve(self, config: TrustConfig, verified, candidate=None):
        try:
            if candidate is not None:
                identifier(candidate)
            with self.connection() as connection:
                metadata = connection.execute("SELECT provider_id,issuer,audience,revision FROM registry_metadata WHERE singleton=1").fetchone()
                if metadata[:3] != (config.provider_id, config.issuer, AUDIENCE):
                    raise RegistryError("registry_trust_mismatch")
                binding = connection.execute("""SELECT b.enabled,p.enabled,p.principal_id,p.principal_type
                    FROM registry_binding b JOIN registry_principal p ON p.principal_id=b.principal_id
                    WHERE b.issuer=? AND b.external_subject=? AND b.client_id=?""",
                    (config.issuer, verified.subject, verified.client_id)).fetchone()
                if binding is None:
                    raise Rejected("binding_unknown")
                if not binding[0]:
                    raise Rejected("binding_disabled")
                if not binding[1] or binding[3] != "workload":
                    raise Rejected("principal_disabled")
                principal = identifier(binding[2])
                memberships = tuple(r[0] for r in connection.execute("""SELECT m.organization_id
                    FROM registry_membership m JOIN registry_organization o ON o.organization_id=m.organization_id
                    WHERE m.principal_id=? AND m.enabled=1 AND o.enabled=1 ORDER BY m.organization_id""", (principal,)))
                if candidate is None:
                    if len(memberships) != 1:
                        raise Rejected("organization_rejected", 403)
                    candidate = memberships[0]
                if candidate not in memberships or candidate not in config.allowed_organization_ids:
                    raise Rejected("organization_rejected", 403)
                identifier(candidate)
                grants = {r[0] for r in connection.execute("""SELECT permission FROM registry_permission
                    WHERE principal_id=? AND organization_id=? AND enabled=1""", (principal, candidate))}
                if PERMISSION not in grants:
                    raise Rejected("policy_rejected", 403)
                return ResolvedPolicy(principal, candidate, (PERMISSION,), metadata[3])
        except RegistryError:
            raise Rejected("registry_unavailable", 503) from None

    def mutate(self, operation, target, organization=None, permission=None, operator=None):
        identifier(target)
        if operator is not None:
            identifier(operator)
        if operation not in OPERATIONS:
            raise RegistryError("unsupported_operation")
        membership = operation.endswith("membership")
        grant = operation.endswith("permission")
        if membership or grant:
            identifier(organization)
        elif organization is not None:
            raise RegistryError("unexpected_organization")
        if grant:
            if not isinstance(permission, str) or not PERMISSION_ID.fullmatch(permission):
                raise RegistryError("invalid_permission")
        elif permission is not None:
            raise RegistryError("unexpected_permission")
        enabled = operation.startswith(("enable-", "grant-"))
        with self.connection(write=True) as connection:
            now = timestamp()
            if membership:
                connection.execute("""INSERT INTO registry_membership VALUES (?,?,?,1,?)
                    ON CONFLICT(principal_id,organization_id) DO UPDATE SET enabled=excluded.enabled,
                    version=registry_membership.version+1,updated_at=excluded.updated_at""", (target, organization, int(enabled), now))
            elif grant:
                connection.execute("""INSERT INTO registry_permission VALUES (?,?,?,?,1,?)
                    ON CONFLICT(principal_id,organization_id,permission) DO UPDATE SET enabled=excluded.enabled,
                    version=registry_permission.version+1,updated_at=excluded.updated_at""", (target, organization, permission, int(enabled), now))
            else:
                table, key = ("registry_binding", "binding_id") if operation.endswith("binding") else ("registry_principal", "principal_id")
                # Only closed server-owned SQL identifiers; all values remain parameters.
                cursor = connection.execute(f"UPDATE {table} SET enabled=?,version=version+1,updated_at=? WHERE {key}=?", (int(enabled), now, target))
                if cursor.rowcount != 1:
                    raise RegistryError("unknown_target")
            connection.execute("UPDATE registry_metadata SET revision=revision+1 WHERE singleton=1")
            self.append_change(connection, operation, target, organization, permission, enabled, operator)
            self.validate(connection)
            revision = connection.execute("SELECT revision FROM registry_metadata WHERE singleton=1").fetchone()[0]
        return {"committed": True, "revision": revision, "operation": operation, "operator_verified": False}

    def sanitized(self):
        with self.connection() as connection:
            return {"contract_version": VERSION,
                    "revision": connection.execute("SELECT revision FROM registry_metadata WHERE singleton=1").fetchone()[0],
                    "principals": connection.execute("SELECT principal_id,principal_type,enabled,version FROM registry_principal ORDER BY principal_id").fetchall(),
                    "bindings": connection.execute("SELECT binding_id,principal_id,enabled,version FROM registry_binding ORDER BY binding_id").fetchall(),
                    "memberships": connection.execute("SELECT principal_id,organization_id,enabled,version FROM registry_membership ORDER BY principal_id,organization_id").fetchall(),
                    "grants": connection.execute("SELECT principal_id,organization_id,permission,enabled,version FROM registry_permission ORDER BY principal_id,organization_id,permission").fetchall(),
                    "operator_verified": False}
