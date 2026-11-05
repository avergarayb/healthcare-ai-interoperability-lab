"""Versioned synthetic policy snapshots. Mutations are test administration only."""
from dataclasses import dataclass, fields, replace
import re
from threading import RLock
from uuid import uuid4

from .audit import AuditSink
from .models import (
    ConnectorAuditEvent, ConnectorDefinition, ConnectorFailure, ConnectorInstance,
    ConnectorPrincipalGrant, CredentialReference, ExternalResourceGrant, Outcome,
    Phase, QualifiedExternalResource, Reason, RegisteredPrincipal, TenantConnectorBinding,
)

TABLE_TYPES = {
    "principals": RegisteredPrincipal, "definitions": ConnectorDefinition,
    "instances": ConnectorInstance, "bindings": TenantConnectorBinding,
    "resources": QualifiedExternalResource, "external_grants": ExternalResourceGrant,
    "principal_grants": ConnectorPrincipalGrant, "credentials": CredentialReference,
}
SAFE_ID = re.compile(r"[A-Za-z0-9.-]{1,64}\Z")


@dataclass(frozen=True, slots=True)
class PolicySnapshot:
    principals: tuple[RegisteredPrincipal, ...]
    definitions: tuple[ConnectorDefinition, ...]
    instances: tuple[ConnectorInstance, ...]
    bindings: tuple[TenantConnectorBinding, ...]
    resources: tuple[QualifiedExternalResource, ...]
    external_grants: tuple[ExternalResourceGrant, ...]
    principal_grants: tuple[ConnectorPrincipalGrant, ...]
    credentials: tuple[CredentialReference, ...]
    revision: int = 1

    def __post_init__(self):
        if type(self.revision) is not int or self.revision < 1:
            raise ValueError("invalid policy revision")
        for table, row_type in TABLE_TYPES.items():
            rows = getattr(self, table)
            if type(rows) is not tuple or any(type(row) is not row_type for row in rows):
                raise ValueError("typed immutable rows required")
            for row in rows:
                for attr in fields(row):
                    value = getattr(row, attr.name)
                    if isinstance(value, (dict, list, set)):
                        raise ValueError("mutable policy field")
                    if attr.name.endswith("_id") or attr.name == "credential_ref":
                        if value is None and attr.name == "parent_id":
                            continue
                        if not isinstance(value, str) or not SAFE_ID.fullmatch(value):
                            raise ValueError("invalid registered identifier")


def unique(rows, field, value):
    matches = [row for row in rows if getattr(row, field) == value]
    if len(matches) != 1:
        raise ConnectorFailure(Reason.POLICY if matches else Reason.NOT_REGISTERED)
    return matches[0]


class SyntheticPolicyStore:
    def __init__(self, snapshot: PolicySnapshot, audit: AuditSink, clock):
        self.lock = RLock()
        self._snapshot, self._audit, self._clock = snapshot, audit, clock

    def snapshot(self) -> PolicySnapshot:
        with self.lock:
            return self._snapshot

    def delivery_guard(self):
        return self.lock

    def replace_rows(self, table: str, rows: tuple, *, expected_revision: int) -> int:
        """Server/test-only CAS; not an authenticated enterprise admin interface."""
        with self.lock:
            if table not in TABLE_TYPES:
                raise ValueError("unknown policy table")
            if self._snapshot.revision != expected_revision:
                raise ConnectorFailure(Reason.STALE)
            candidate = replace(self._snapshot, **{table: rows}, revision=expected_revision + 1)
            self._audit.append(ConnectorAuditEvent(
                str(uuid4()), str(uuid4()), self._clock(), Phase.CHANGE,
                Outcome.LOCAL_ALLOW, Reason.CHANGE, candidate.revision,
            ))
            self._snapshot = candidate
            return candidate.revision
