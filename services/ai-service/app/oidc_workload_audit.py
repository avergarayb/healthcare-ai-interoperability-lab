"""Additive workload-only audit. Never writes the legacy SECURITY_AUDIT_V1 store."""
from __future__ import annotations

import sqlite3
import uuid
import threading
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from app.oidc_config import ID, ROUTE, Rejected

VERSION = "oidc-workload-security-audit-v1"
REASONS = frozenset({"access_granted", "credential_missing", "credential_ambiguous", "credential_malformed",
                     "credential_conflict", "configuration_incomplete", "provider_disabled", "provider_untrusted",
                     "provider_unavailable", "discovery_mismatch", "keys_invalid", "keys_unavailable", "unknown_key",
                     "algorithm_rejected", "key_source_rejected", "verification_rejected", "token_expired",
                     "time_rejected", "purpose_rejected", "audience_rejected", "binding_unknown", "binding_disabled",
                     "principal_disabled", "organization_rejected", "policy_rejected"})


class WorkloadAudit:
    def __init__(self, path: str):
        self.path = Path(path)
        if not path or path == ":memory:" or self.path.is_symlink():
            raise ValueError("dedicated audit file required")
        self._writer = threading.Lock()

    def append(self, *, reason, correlation, provider=None, context=None):
        with self._writer:
            return self._append(reason=reason, correlation=correlation, provider=provider, context=context)

    def _append(self, *, reason, correlation, provider=None, context=None):
        try:
            if reason not in REASONS or str(uuid.UUID(correlation, version=4)) != correlation:
                raise ValueError("invalid audit event")
            if provider is not None and not ID.fullmatch(provider):
                raise ValueError("invalid provider")
            allowed = reason == "access_granted"
            if allowed != (context is not None):
                raise ValueError("invalid actor")
            principal = None if context is None else context.internal_principal_id
            organization = None if context is None else context.organization_id
            if context is not None and (not ID.fullmatch(principal) or not ID.fullmatch(organization)):
                raise ValueError("invalid actor")
            if self.path.is_symlink():
                raise ValueError("symlink audit file")
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with closing(sqlite3.connect(self.path, timeout=1)) as connection:
                try:
                    tables = {r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                    table = "oidc_workload_security_audit_v1"
                    if tables - {table}:
                        raise ValueError("foreign database schema")
                    if connection.execute("PRAGMA journal_mode=WAL").fetchone()[0].lower() != "wal":
                        raise ValueError("WAL required")
                    connection.execute("PRAGMA busy_timeout=1000")
                    connection.execute("BEGIN IMMEDIATE")
                    if not tables:
                        connection.execute("""CREATE TABLE oidc_workload_security_audit_v1 (
                            event_id TEXT PRIMARY KEY, timestamp_utc TEXT NOT NULL,
                            contract_version TEXT NOT NULL CHECK(contract_version='oidc-workload-security-audit-v1'),
                            event_type TEXT NOT NULL CHECK(event_type='workload_authentication'),
                            source_service TEXT NOT NULL CHECK(source_service='ai-service'),
                            action TEXT NOT NULL CHECK(action='authenticate_workload'),
                            route TEXT NOT NULL CHECK(route='/iam-lab/v1/workload-context'),
                            outcome TEXT NOT NULL CHECK(outcome IN ('allowed','denied')),
                            reason_code TEXT NOT NULL, actor_type TEXT NOT NULL CHECK(actor_type IN ('workload','anonymous')),
                            actor_id TEXT, organization_id TEXT, provider_id TEXT, correlation_id TEXT NOT NULL,
                            CHECK((outcome='allowed' AND actor_type='workload' AND actor_id IS NOT NULL AND organization_id IS NOT NULL)
                               OR (outcome='denied' AND actor_type='anonymous' AND actor_id IS NULL AND organization_id IS NULL)))""")
                        connection.execute("PRAGMA user_version=1")
                    if connection.execute("PRAGMA user_version").fetchone()[0] != 1:
                        raise ValueError("unsupported audit schema")
                    connection.execute("INSERT INTO oidc_workload_security_audit_v1 VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                        str(uuid.uuid4()), datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"), VERSION,
                        "workload_authentication", "ai-service", "authenticate_workload", ROUTE,
                        "allowed" if allowed else "denied", reason, "workload" if allowed else "anonymous",
                        principal, organization, provider, correlation))
                    connection.commit()
                except BaseException:
                    connection.rollback()
                    raise
        except (ValueError, TypeError, OSError, sqlite3.DatabaseError):
            raise Rejected("audit_unavailable", 503) from None
