"""Explicitly initialized, isolated SQLite laboratory policy and audit storage."""
from contextlib import closing, contextmanager
from contextvars import ContextVar
from dataclasses import fields, replace
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
import sqlite3
from threading import BoundedSemaphore, RLock

from .control_types import CredentialState, InstanceState, decode, instant
from .models import ConnectorFailure, ConnectorInstance, Reason
from .registry import PolicySnapshot, SAFE_ID, TABLE_TYPES

VERSION = "enterprise-connector-control-plane-v1"
APPLICATION_ID = 0x45434133
MIGRATION = Path(__file__).parent / "migrations/001_control_plane.sql"
TABLES = {
    "definitions": ("eca_definition", "definition_id"), "principals": ("eca_principal", "principal_id"),
    "bindings": ("eca_binding", "binding_id"), "resources": ("eca_resource", "resource_id"),
    "credentials": ("eca_credential", "reference_id"),
    "external_grants": ("eca_external_grant", "grant_id"),
    "principal_grants": ("eca_principal_grant", "grant_id"),
}


def unavailable():
    return ConnectorFailure(Reason.POLICY, unavailable=True)


def migration_checksum():
    # New migration identity is stable across LF/CRLF checkouts; history is untouched.
    return sha256(MIGRATION.read_text(encoding="utf-8").replace("\r\n", "\n").encode("utf-8")).hexdigest()


def ddl(connection):
    return connection.execute("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type,name").fetchall()


@lru_cache(maxsize=1)
def expected_ddl():
    with closing(sqlite3.connect(":memory:")) as connection:
        connection.executescript(MIGRATION.read_text(encoding="utf-8"))
        return ddl(connection)


def validate_record(record):
    for item in fields(record):
        value = getattr(record, item.name)
        if item.name.endswith("_id") or item.name == "credential_ref":
            if value is None and item.name == "parent_id":
                continue
            if type(value) is not str or not SAFE_ID.fullmatch(value):
                raise ValueError("invalid identifier")
        if item.name in {"enabled"} and type(value) is not bool:
            raise ValueError("boolean required")
        if item.name == "version" and (type(value) is not int or value < 1):
            raise ValueError("version required")
        if item.name in {"operations", "gates", "recipients", "purposes", "classifications", "allowed_mimes"}:
            if type(value) is not frozenset or len(value) > 32:
                raise ValueError("bounded immutable set required")
            if any(not isinstance(v, str) or not 1 <= len(v) <= 80 for v in value):
                raise ValueError("invalid policy value")
    # The existing snapshot validates nested mutability and typed row contracts.


class SQLitePolicyStore:
    def __init__(self, path, *, test_owned_root, clock, forbidden_paths=(), fault=None):
        self.path, self.root = Path(path), Path(test_owned_root)
        self.clock, self.fault = clock, fault or (lambda stage: None)
        self.lock, self._connections = RLock(), BoundedSemaphore(4)
        self._current = ContextVar("eca_sqlite_transaction_" + str(id(self)), default=None)
        self._forbidden = {Path(p).resolve() for p in forbidden_paths if p}
        self._safe_path(exists=False)

    def _safe_path(self, *, exists):
        try:
            path, root = self.path, self.root
            if (not path.is_absolute() or not root.is_absolute() or not root.is_dir()
                    or path.parent != root or path.suffix != ".sqlite3"
                    or path != path.resolve() or root != root.resolve()
                    or path.name.endswith(("-wal", "-shm", "-journal"))
                    or path.resolve() in self._forbidden):
                raise ValueError("dedicated test-owned path required")
            for component in (path, *path.parents):
                if component.is_symlink() or (hasattr(component, "is_junction") and component.is_junction()):
                    raise ValueError("path alias rejected")
            if exists and (not path.is_file() or path.stat().st_nlink != 1):
                raise ValueError("store missing or linked")
            return path
        except (OSError, ValueError):
            raise unavailable() from None

    def validate(self, connection):
        if (connection.execute("PRAGMA application_id").fetchone()[0] != APPLICATION_ID
                or connection.execute("PRAGMA user_version").fetchone()[0] != 1
                or connection.execute("PRAGMA journal_mode").fetchone()[0].lower() != "wal"
                or ddl(connection) != expected_ddl()
                or connection.execute("PRAGMA quick_check(1)").fetchone()[0] != "ok"
                or connection.execute("PRAGMA foreign_key_check").fetchone() is not None):
            raise unavailable()
        meta = connection.execute("SELECT contract_version,migration_sha256,revision FROM eca_metadata WHERE singleton=1").fetchone()
        if not meta or meta[0] != VERSION or meta[1] != migration_checksum():
            raise unavailable()
        count, first, last = connection.execute("SELECT count(*),min(revision),max(revision) FROM eca_admin_audit WHERE outcome='allowed'").fetchone()
        if count != meta[2] or first != 1 or last != meta[2]:
            raise unavailable()

    @contextmanager
    def connection(self, *, write=False):
        current = self._current.get()
        if current is not None:
            yield current
            return
        if not self._connections.acquire(timeout=0.2):
            raise unavailable()
        connection = None
        token = None
        try:
            path = self._safe_path(exists=True)
            connection = sqlite3.connect(path.as_uri() + ("?mode=rw" if write else "?mode=ro"), uri=True, timeout=0.1)
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA trusted_schema=OFF")
            connection.execute("PRAGMA busy_timeout=100")
            if not write:
                connection.execute("PRAGMA query_only=ON")
            connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            self.validate(connection)
            token = self._current.set(connection)
            yield connection
            if write:
                self.validate(connection)
                self.fault("before_commit")
                connection.commit()
        except ConnectorFailure:
            raise
        except (OSError, ValueError, TypeError, sqlite3.Error, KeyError, OverflowError):
            raise unavailable() from None
        finally:
            if token is not None:
                self._current.reset(token)
            if connection is not None:
                connection.rollback()
                connection.close()
            self._connections.release()

    @contextmanager
    def delivery_guard(self):
        # SQLite's writer reservation orders the final check with independent writers.
        with self.lock, self.connection(write=True):
            yield

    def _snapshot(self, connection):
        result = {}
        for name, (table, key) in TABLES.items():
            rows = connection.execute("SELECT * FROM " + table + " ORDER BY " + key + " LIMIT 1025").fetchall()
            if len(rows) > 1024:
                raise unavailable()
            columns = [r[1] for r in connection.execute("PRAGMA table_info(" + table + ")")]
            records = []
            for values in rows:
                row = dict(zip(columns, values))
                record = decode(TABLE_TYPES[name], row["payload"])
                validate_record(record)
                for column in (key, "organization_id", "instance_id", "resource_id", "principal_id", "parent_id", "version"):
                    if column in row and hasattr(record, column) and getattr(record, column) != row[column]:
                        raise unavailable()
                if name == "credentials":
                    live = (row["state"] == CredentialState.ACTIVE.value
                            and self.clock() < min(record.expires_at, instant(row["review_due_at"])))
                    record = replace(record, enabled=record.enabled and live)
                records.append(record)
            result[name] = tuple(records)
        rows = connection.execute("SELECT instance_id,organization_id,definition_id,binding_id,credential_ref,state,version FROM eca_instance ORDER BY instance_id LIMIT 1025").fetchall()
        if len(rows) > 1024:
            raise unavailable()
        result["instances"] = tuple(ConnectorInstance(r[0], r[1], r[2], r[3] or "unbound", r[4] or "unbound",
                                                       enabled=r[5] == InstanceState.ACTIVE.value,
                                                       lifecycle_status=r[5].lower(), version=r[6]) for r in rows)
        revision = connection.execute("SELECT revision FROM eca_metadata WHERE singleton=1").fetchone()[0]
        return PolicySnapshot(**result, revision=revision)

    def snapshot(self):
        try:
            with self.connection() as connection:
                return self._snapshot(connection)
        except ConnectorFailure:
            raise
        except (ValueError, TypeError, AttributeError, KeyError):
            raise unavailable() from None
