"""Mandatory durable connector audit, never IAM or clinical audit."""
from uuid import UUID
import sqlite3

from .control_types import utc
from .models import ConnectorAuditEvent, ConnectorFailure, ConnectorOperation, Outcome, Phase, Reason
from .registry import SAFE_ID


class SQLiteConnectorAudit:
    def __init__(self, store):
        self.store = store
        self.fail_phases = set()  # Composition-only deterministic fault injection.

    def append(self, event):
        try:
            if (type(event) is not ConnectorAuditEvent or event.contract_version != "connector-security-audit-v1"
                    or type(event.phase) is not Phase or event.phase == Phase.CHANGE
                    or type(event.outcome) is not Outcome or type(event.reason) is not Reason
                    or event.phase in self.fail_phases
                    or type(event.policy_revision) is not int or event.policy_revision < 1):
                raise ValueError("closed event required")
            for value in (event.event_id, event.correlation_id):
                if str(UUID(value, version=4)) != value:
                    raise ValueError("UUID required")
            for value in (event.principal_id, event.organization_id, event.instance_id, event.resource_id):
                if value is not None and (type(value) is not str or not SAFE_ID.fullmatch(value)):
                    raise ValueError("internal reference required")
            if (event.principal_id is None) != (event.organization_id is None):
                raise ValueError("invalid actor")
            if event.operation is not None and type(event.operation) is not ConnectorOperation:
                raise ValueError("closed operation required")
            with self.store.connection(write=True) as connection:
                self.store.fault("before_access_audit")
                connection.execute("INSERT INTO eca_access_audit VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                    event.event_id, event.correlation_id, utc(event.timestamp), event.contract_version,
                    event.phase.value, event.outcome.value, event.reason.value, event.policy_revision,
                    "anonymous" if event.principal_id is None else "workload", event.principal_id,
                    event.organization_id, event.instance_id, event.resource_id,
                    None if event.operation is None else event.operation.value,
                ))
        except (ConnectorFailure, ValueError, TypeError, AttributeError, sqlite3.Error):
            raise ConnectorFailure(Reason.AUDIT, unavailable=True) from None
