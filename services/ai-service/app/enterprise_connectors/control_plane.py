"""Synthetic, internal administration. No routes, CLI, corporate login or secrets."""
from contextlib import closing
from dataclasses import replace
import sqlite3
from uuid import uuid4

from .control_types import AdministrativeContext, CredentialMetadata, CredentialState as CS, InstanceState as IS, encode, utc
from .models import ConnectorFailure, ConnectorOperation as Op, Gate, Reason, RegisteredPrincipal
from .policy import in_scope
from .registry import SAFE_ID, TABLE_TYPES, unique
from .sqlite_store import APPLICATION_ID, MIGRATION, TABLES, VERSION, migration_checksum, unavailable, validate_record

ADMIN_OPERATIONS = frozenset({"initialize", "register_definition", "register_principal", "create_instance",
    "register_binding", "register_resource", "register_external_grant", "register_principal_grant",
    "register_credential", "submit", "approve", "activate", "suspend", "revoke", "offboard",
    "change_grant", "activate_credential", "suspend_credential", "revoke_credential", "expire_credential", "rotate"})
READ_OPERATIONS = frozenset({Op.RESOLVE, Op.METADATA, Op.CHILDREN, Op.READ, Op.PROVENANCE})


def identifier(value):
    if type(value) is not str or not SAFE_ID.fullmatch(value):
        raise ConnectorFailure(Reason.POLICY)
    return value


class ControlPlane:
    def __init__(self, store, authority):
        self.store, self.authority = store, authority

    def _actor(self, context, operation):
        if type(context) is not AdministrativeContext or not self.authority.recognizes(context):
            raise ConnectorFailure(Reason.IDENTITY)
        identifier(context.principal_id)
        identifier(context.organization_id)
        try:
            utc(context.expires_at)
        except (ValueError, TypeError, AttributeError):
            raise ConnectorFailure(Reason.IDENTITY) from None
        if (context.expires_at <= self.store.clock()
                or context.role not in {"administrator", "operator"}
                or context.actor_type != ("synthetic_administrator" if context.role == "administrator" else "synthetic_operator")):
            raise ConnectorFailure(Reason.IDENTITY)
        if context.role == "operator" and operation not in {"read", "suspend", "suspend_credential"}:
            raise ConnectorFailure(Reason.GRANT)
        return context

    def _audit(self, connection, actor, operation, correlation, previous, revision, meta, *, allowed=True, reason="accepted"):
        if operation not in ADMIN_OPERATIONS and operation != "read":
            raise ConnectorFailure(Reason.POLICY)
        self.store.fault("before_admin_audit")
        connection.execute("INSERT INTO eca_admin_audit VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            str(uuid4()), correlation, utc(self.store.clock()), "enterprise-connector-administration-audit-v1",
            "anonymous" if actor is None else actor.actor_type,
            None if actor is None else actor.principal_id, None if actor is None else actor.organization_id,
            operation, meta.get("entity_type", "control_plane"), meta.get("entity_id"), meta.get("related_entity_id"), previous, revision,
            meta.get("previous_version"), meta.get("version"), meta.get("previous_state"), meta.get("state"),
            "allowed" if allowed else "denied", reason,
        ))

    def _deny(self, actor, operation, correlation, reason):
        with self.store.connection(write=True) as connection:
            revision = connection.execute("SELECT revision FROM eca_metadata WHERE singleton=1").fetchone()[0]
            # Unknown/cross-org targets and unverified input are never recorded.
            self._audit(connection, actor, operation, correlation, revision, revision, {}, allowed=False, reason=reason.value)

    def initialize(self, context):
        actor = self._actor(context, "initialize")
        path = self.store._safe_path(exists=False)
        try:
            with path.open("xb"):
                pass
            with closing(sqlite3.connect(path, timeout=0.1)) as connection:
                connection.execute("PRAGMA foreign_keys=ON")
                if connection.execute("PRAGMA journal_mode=WAL").fetchone()[0].lower() != "wal":
                    raise unavailable()
                connection.execute("BEGIN IMMEDIATE")
                try:
                    for statement in MIGRATION.read_text(encoding="utf-8").split(";"):
                        if statement.strip():
                            connection.execute(statement)
                    connection.execute("PRAGMA user_version=1")
                    connection.execute("PRAGMA application_id=" + str(APPLICATION_ID))
                    connection.execute("INSERT INTO eca_metadata VALUES (1,?,?,1)", (VERSION, migration_checksum()))
                    self._audit(connection, actor, "initialize", str(uuid4()), 0, 1, {"entity_type": "store"})
                    self.store.validate(connection)
                    self.store.fault("before_commit")
                    connection.commit()
                except BaseException:
                    connection.rollback()
                    raise
        except (OSError, ValueError, TypeError, sqlite3.Error):
            raise unavailable() from None

    def _mutate(self, context, operation, expected_revision, action):
        if self.store._current.get() is not None:
            # Administration must own its commit, never join a data-plane audit transaction.
            raise unavailable()
        correlation, actor = str(uuid4()), None
        try:
            actor = self._actor(context, "read")
            self._actor(context, operation)
            with self.store.connection(write=True) as connection:
                previous = connection.execute("SELECT revision FROM eca_metadata WHERE singleton=1").fetchone()[0]
                if type(expected_revision) is not int or expected_revision != previous:
                    raise ConnectorFailure(Reason.STALE)
                meta = action(connection, actor.organization_id)
                self.store.fault("after_entity_write")
                connection.execute("UPDATE eca_metadata SET revision=revision+1 WHERE singleton=1 AND revision=?", (previous,))
                self._audit(connection, actor, operation, correlation, previous, previous + 1, meta)
                return {"committed": True, "revision": previous + 1, **meta}
        except ConnectorFailure as failure:
            if not failure.unavailable:
                self._deny(actor, operation, correlation, failure.reason)
            raise
        except (ValueError, TypeError, AttributeError):
            self._deny(actor, operation, correlation, Reason.POLICY)
            raise ConnectorFailure(Reason.POLICY) from None

    @staticmethod
    def _row(connection, table, key, value, org):
        identifier(value)
        cursor = connection.execute("SELECT * FROM " + table + " WHERE " + key + "=? AND organization_id=?", (value, org))
        values = cursor.fetchone()
        if values is None:
            raise ConnectorFailure(Reason.RESOURCE)
        return dict(zip((c[0] for c in cursor.description), values))

    def _instance(self, connection, instance_id, org):
        return self._row(connection, "eca_instance", "instance_id", instance_id, org)

    @staticmethod
    def _touch(connection, instance_id):
        connection.execute("UPDATE eca_instance SET version=version+1,approved_version=CASE WHEN state='ACTIVE' THEN approved_version ELSE NULL END WHERE instance_id=?", (instance_id,))

    def register(self, context, kind, record, *, expected_revision):
        if kind not in {"definitions", "principals", "bindings", "resources", "external_grants", "principal_grants"}:
            raise ConnectorFailure(Reason.POLICY)
        operation = {"definitions": "register_definition", "principals": "register_principal", "bindings": "register_binding",
                     "resources": "register_resource", "external_grants": "register_external_grant", "principal_grants": "register_principal_grant"}[kind]
        def action(connection, org):
            if type(record) is not TABLE_TYPES[kind]:
                raise ConnectorFailure(Reason.POLICY)
            validate_record(record)
            if kind != "definitions" and record.organization_id != org:
                raise ConnectorFailure(Reason.ORGANIZATION)
            if hasattr(record, "version") and record.version != 1:
                raise ConnectorFailure(Reason.STALE)
            if kind == "definitions":
                if not record.operations or not record.operations <= READ_OPERATIONS:
                    raise ConnectorFailure(Reason.OPERATION)
                connection.execute("INSERT INTO eca_definition VALUES (?,?,?,?)", (record.definition_id, org, record.version, encode(record)))
                entity_id = record.definition_id
            elif kind == "principals":
                if record.principal_type != "workload":
                    raise ConnectorFailure(Reason.PRINCIPAL_TYPE)
                connection.execute("INSERT INTO eca_principal VALUES (?,?,?)", (record.principal_id, org, encode(record)))
                entity_id = record.principal_id
            else:
                instance = self._instance(connection, record.instance_id, org)
                if instance["state"] in {IS.REVOKED.value, IS.OFFBOARDED.value}:
                    raise ConnectorFailure(Reason.POLICY)
                if kind == "bindings":
                    if instance["state"] != IS.DRAFT.value or instance["binding_id"] is not None:
                        raise ConnectorFailure(Reason.BINDING)
                    if (record.mode, record.provider, record.cloud) != ("application", "synthetic-documents", "synthetic"):
                        raise ConnectorFailure(Reason.MODE)
                    connection.execute("INSERT INTO eca_binding VALUES (?,?,?,?,?)", (record.binding_id, org, record.instance_id, encode(record), record.version))
                    connection.execute("UPDATE eca_instance SET binding_id=? WHERE instance_id=?", (record.binding_id, record.instance_id))
                    entity_id = record.binding_id
                else:
                    snapshot = self.store._snapshot(connection)
                    binding = unique(snapshot.bindings, "binding_id", instance["binding_id"])
                    if kind == "resources":
                        if (record.kind != "registered" or record.resource_type not in {"folder", "document"}
                                or (record.tenant_id, record.provider, record.cloud) != (binding.tenant_id, binding.provider, binding.cloud)):
                            raise ConnectorFailure(Reason.RESOURCE)
                        if record.parent_id is not None:
                            parent = unique(snapshot.resources, "resource_id", record.parent_id)
                            if parent.instance_id != record.instance_id or parent.organization_id != org or parent.resource_type != "folder":
                                raise ConnectorFailure(Reason.RESOURCE)
                        connection.execute("INSERT INTO eca_resource VALUES (?,?,?,?,?,?)", (record.resource_id, org, record.instance_id, record.parent_id, record.version, encode(record)))
                        entity_id = record.resource_id
                    else:
                        resource = unique(snapshot.resources, "resource_id", record.resource_id)
                        definition = unique(snapshot.definitions, "definition_id", instance["definition_id"])
                        if (resource.organization_id != org or resource.instance_id != record.instance_id
                                or record.mode != "application" or record.scope not in {"exact", "subtree"}
                                or not record.operations or not record.operations <= definition.operations
                                or record.expires_at <= self.store.clock()):
                            raise ConnectorFailure(Reason.GRANT)
                        if kind == "principal_grants":
                            principal = unique(snapshot.principals, "principal_id", record.principal_id)
                            if (principal.organization_id != org or not principal.enabled or not record.gates <= {Gate.READ, Gate.DELIVERY}
                                    or not record.purposes or not record.recipients or not record.classifications):
                                raise ConnectorFailure(Reason.GRANT)
                            connection.execute("INSERT INTO eca_principal_grant VALUES (?,?,?,?,?,?,?)", (record.grant_id, org, record.instance_id, record.resource_id, record.principal_id, record.version, encode(record)))
                        else:
                            if record.profile != "synthetic-selected-read":
                                raise ConnectorFailure(Reason.GRANT)
                            connection.execute("INSERT INTO eca_external_grant VALUES (?,?,?,?,?,?)", (record.grant_id, org, record.instance_id, record.resource_id, record.version, encode(record)))
                        entity_id = record.grant_id
                self._touch(connection, record.instance_id)
            return {"entity_type": kind, "entity_id": entity_id, "previous_version": 0, "version": 1}
        return self._mutate(context, operation, expected_revision, action)

    def create_instance(self, context, instance_id, definition_id, *, expected_revision):
        def action(connection, org):
            identifier(instance_id)
            self._row(connection, "eca_definition", "definition_id", definition_id, org)
            connection.execute("INSERT INTO eca_instance VALUES (?,?,?,NULL,NULL,'DRAFT',1,NULL)", (instance_id, org, definition_id))
            return {"entity_type": "instances", "entity_id": instance_id, "previous_version": 0, "version": 1, "state": IS.DRAFT.value}
        return self._mutate(context, "create_instance", expected_revision, action)

    def register_credential(self, context, metadata: CredentialMetadata, *, expected_revision):
        def action(connection, org):
            self._insert_credential(connection, org, metadata)
            instance = self._instance(connection, metadata.reference.instance_id, org)
            if instance["credential_ref"] is not None:
                raise ConnectorFailure(Reason.CREDENTIAL)
            connection.execute("UPDATE eca_instance SET credential_ref=? WHERE instance_id=?", (metadata.reference.reference_id, instance["instance_id"]))
            self._touch(connection, instance["instance_id"])
            return {"entity_type": "credentials", "entity_id": metadata.reference.reference_id, "previous_version": 0, "version": 1, "state": CS.PENDING.value}
        return self._mutate(context, "register_credential", expected_revision, action)

    def _insert_credential(self, connection, org, metadata, *, active=False, version=1):
        if type(metadata) is not CredentialMetadata or metadata.state != CS.PENDING or metadata.reference_type != "synthetic":
            raise ConnectorFailure(Reason.CREDENTIAL)
        record = metadata.reference
        if type(record) is not TABLE_TYPES["credentials"]:
            raise ConnectorFailure(Reason.CREDENTIAL)
        validate_record(record)
        instance = self._instance(connection, record.instance_id, org)
        if instance["state"] in {IS.REVOKED.value, IS.OFFBOARDED.value}:
            raise ConnectorFailure(Reason.CREDENTIAL)
        binding = unique(self.store._snapshot(connection).bindings, "binding_id", metadata.binding_id)
        if (record.organization_id != org or instance["binding_id"] != metadata.binding_id
                or (record.tenant_id, record.client_id, record.service_principal_id, record.provider, record.cloud, record.mode)
                != (binding.tenant_id, binding.client_id, binding.service_principal_id, binding.provider, binding.cloud, binding.mode)
                or record.profile != "synthetic-selected-read" or not metadata.custody_ref.startswith("synthetic-custody.")
                or not SAFE_ID.fullmatch(metadata.custody_ref)
                or min(record.expires_at, metadata.review_due_at) <= self.store.clock()):
            raise ConnectorFailure(Reason.CREDENTIAL)
        record = replace(record, enabled=active, version=version)
        connection.execute("INSERT INTO eca_credential VALUES (?,?,?,?,?,?,?,?,?,?)", (
            record.reference_id, org, record.instance_id, metadata.binding_id, "synthetic", metadata.custody_ref,
            utc(metadata.review_due_at), CS.ACTIVE.value if active else CS.PENDING.value, version, encode(record)))

    def _ready(self, connection, instance):
        snapshot = self.store._snapshot(connection)
        definition = unique(snapshot.definitions, "definition_id", instance["definition_id"])
        if not definition.enabled:
            raise ConnectorFailure(Reason.NOT_REGISTERED)
        binding = unique(snapshot.bindings, "binding_id", instance["binding_id"])
        credential = unique(snapshot.credentials, "reference_id", instance["credential_ref"])
        if not binding.enabled or not credential.enabled or self.store.clock() >= credential.expires_at:
            raise ConnectorFailure(Reason.CREDENTIAL)
        for grant in snapshot.principal_grants:
            if (grant.instance_id != instance["instance_id"] or not grant.enabled or grant.expires_at <= self.store.clock()
                    or not {Gate.READ, Gate.DELIVERY} <= grant.gates):
                continue
            principal = unique(snapshot.principals, "principal_id", grant.principal_id)
            for resource in snapshot.resources:
                if resource.instance_id != instance["instance_id"] or not resource.enabled or not in_scope(snapshot, resource, grant.resource_id, grant.scope):
                    continue
                if not principal.enabled or resource.classification not in grant.classifications:
                    continue
                for external in snapshot.external_grants:
                    if (external.instance_id == instance["instance_id"] and external.enabled and external.expires_at > self.store.clock()
                            and external.profile == credential.profile and external.operations & grant.operations
                            and in_scope(snapshot, resource, external.resource_id, external.scope)):
                        return
        raise ConnectorFailure(Reason.GRANT)

    def transition(self, context, instance_id, operation, *, expected_revision):
        if operation not in {"submit", "approve", "activate", "suspend", "revoke", "offboard"}:
            raise ConnectorFailure(Reason.POLICY)
        def action(connection, org):
            row = self._instance(connection, instance_id, org)
            old, new, approved = row["state"], row["state"], None
            if operation == "approve" and old in {IS.PENDING_APPROVAL.value, IS.SUSPENDED.value}:
                self._ready(connection, row)
                approved = row["version"] + 1
            elif operation == "activate" and old in {IS.PENDING_APPROVAL.value, IS.SUSPENDED.value}:
                if row["approved_version"] != row["version"]:
                    raise ConnectorFailure(Reason.GRANT)
                self._ready(connection, row)
                new, approved = IS.ACTIVE.value, row["approved_version"]
            elif operation == "submit" and old == IS.DRAFT.value:
                new = IS.PENDING_APPROVAL.value
            elif operation == "suspend" and old == IS.ACTIVE.value:
                new = IS.SUSPENDED.value
            elif operation == "revoke" and old in {IS.DRAFT.value, IS.PENDING_APPROVAL.value, IS.ACTIVE.value, IS.SUSPENDED.value}:
                new = IS.REVOKED.value
            elif operation == "offboard" and old == IS.REVOKED.value:
                new = IS.OFFBOARDED.value
                self._offboard(connection, row)
            else:
                raise ConnectorFailure(Reason.POLICY)
            connection.execute("UPDATE eca_instance SET state=?,version=version+1,approved_version=? WHERE instance_id=?", (new, approved, instance_id))
            return {"entity_type": "instances", "entity_id": instance_id, "previous_version": row["version"], "version": row["version"] + 1,
                    "previous_state": old, "state": new}
        return self._mutate(context, operation, expected_revision, action)

    def change_grant(self, context, kind, grant_id, *, expected_revision, enabled=None, replacement=None):
        if kind not in {"principal_grants", "external_grants"}:
            raise ConnectorFailure(Reason.GRANT)
        def action(connection, org):
            table, _ = TABLES[kind]
            row = self._row(connection, table, "grant_id", grant_id, org)
            instance = self._instance(connection, row["instance_id"], org)
            if instance["state"] in {IS.REVOKED.value, IS.OFFBOARDED.value}:
                raise ConnectorFailure(Reason.GRANT)
            from .control_types import decode
            old = decode(TABLE_TYPES[kind], row["payload"])
            new = replace(old, enabled=enabled, version=old.version + 1) if replacement is None else replacement
            if type(new) is not TABLE_TYPES[kind]:
                raise ConnectorFailure(Reason.GRANT)
            validate_record(new)
            immutable = ("grant_id", "organization_id", "instance_id", "resource_id", "mode")
            if kind == "principal_grants":
                immutable += ("principal_id",)
            if (any(getattr(old, field) != getattr(new, field) for field in immutable)
                    or new.version != old.version + 1 or type(new.enabled) is not bool
                    or not new.operations <= old.operations or new.scope != old.scope
                    or (new.enabled and new.expires_at <= self.store.clock())):
                raise ConnectorFailure(Reason.GRANT)
            if kind == "principal_grants" and (not new.gates <= {Gate.READ, Gate.DELIVERY}
                    or not new.purposes or not new.recipients or not new.classifications):
                raise ConnectorFailure(Reason.GRANT)
            if kind == "external_grants" and new.profile != old.profile:
                raise ConnectorFailure(Reason.GRANT)
            connection.execute("UPDATE " + table + " SET version=?,payload=? WHERE grant_id=?", (new.version, encode(new), grant_id))
            self._touch(connection, row["instance_id"])
            return {"entity_type": kind, "entity_id": grant_id, "previous_version": old.version, "version": new.version,
                    "previous_state": "enabled" if old.enabled else "disabled", "state": "enabled" if new.enabled else "disabled"}
        return self._mutate(context, "change_grant", expected_revision, action)

    def transition_credential(self, context, reference_id, state, *, expected_revision):
        if type(state) is not CS:
            raise ConnectorFailure(Reason.CREDENTIAL)
        operation = {CS.ACTIVE: "activate_credential", CS.SUSPENDED: "suspend_credential", CS.REVOKED: "revoke_credential", CS.EXPIRED: "expire_credential"}.get(state)
        if operation is None:
            raise ConnectorFailure(Reason.CREDENTIAL)
        def action(connection, org):
            from .control_types import decode, instant
            row = self._row(connection, "eca_credential", "reference_id", reference_id, org)
            record = decode(TABLE_TYPES["credentials"], row["payload"])
            allowed = {CS.PENDING.value: {CS.ACTIVE, CS.REVOKED, CS.EXPIRED}, CS.ACTIVE.value: {CS.SUSPENDED, CS.REVOKED, CS.EXPIRED}, CS.SUSPENDED.value: {CS.ACTIVE, CS.REVOKED, CS.EXPIRED}}
            expired = self.store.clock() >= min(record.expires_at, instant(row["review_due_at"]))
            if state not in allowed.get(row["state"], set()) or (state == CS.ACTIVE and expired) or (state == CS.EXPIRED and not expired):
                raise ConnectorFailure(Reason.CREDENTIAL)
            record = replace(record, enabled=state == CS.ACTIVE, version=record.version + 1)
            connection.execute("UPDATE eca_credential SET state=?,version=?,payload=? WHERE reference_id=?", (state.value, record.version, encode(record), reference_id))
            self._touch(connection, record.instance_id)
            return {"entity_type": "credentials", "entity_id": reference_id, "previous_version": row["version"], "version": record.version,
                    "previous_state": row["state"], "state": state.value}
        return self._mutate(context, operation, expected_revision, action)

    def rotate(self, context, old_reference_id, metadata, *, expected_revision):
        def action(connection, org):
            from .control_types import decode
            old = self._row(connection, "eca_credential", "reference_id", old_reference_id, org)
            record = decode(TABLE_TYPES["credentials"], old["payload"])
            instance = self._instance(connection, record.instance_id, org)
            if old["state"] not in {CS.ACTIVE.value, CS.SUSPENDED.value} or instance["credential_ref"] != old_reference_id:
                raise ConnectorFailure(Reason.CREDENTIAL)
            if metadata.reference.instance_id != record.instance_id or metadata.binding_id != old["binding_id"]:
                raise ConnectorFailure(Reason.CREDENTIAL)
            self._insert_credential(connection, org, metadata, active=True, version=record.version + 1)
            retired = replace(record, enabled=False, version=record.version + 1)
            connection.execute("UPDATE eca_credential SET state='REPLACED',version=?,payload=? WHERE reference_id=?", (retired.version, encode(retired), old_reference_id))
            connection.execute("UPDATE eca_instance SET credential_ref=? WHERE instance_id=?", (metadata.reference.reference_id, record.instance_id))
            self._touch(connection, record.instance_id)
            return {"entity_type": "credentials", "entity_id": metadata.reference.reference_id, "related_entity_id": old_reference_id,
                    "previous_version": record.version, "version": retired.version,
                    "previous_state": old["state"], "state": CS.ACTIVE.value}
        return self._mutate(context, "rotate", expected_revision, action)

    def _offboard(self, connection, instance):
        from .control_types import decode
        for name in ("bindings", "resources", "external_grants", "principal_grants", "credentials"):
            table, key = TABLES[name]
            for row_id, payload in connection.execute("SELECT " + key + ",payload FROM " + table + " WHERE instance_id=?", (instance["instance_id"],)).fetchall():
                record = decode(TABLE_TYPES[name], payload)
                record = replace(record, enabled=False, version=record.version + 1)
                connection.execute("UPDATE " + table + " SET version=?,payload=?" + (",state='REVOKED'" if name == "credentials" else "") + " WHERE " + key + "=?", (record.version, encode(record), row_id))

    def metadata(self, context, kind):
        actor = self._actor(context, "read")
        if kind not in TABLES and kind != "instances":
            raise ConnectorFailure(Reason.POLICY)
        table, key = ("eca_instance", "instance_id") if kind == "instances" else TABLES[kind]
        with self.store.connection() as connection:
            columns = {r[1] for r in connection.execute("PRAGMA table_info(" + table + ")")}
            selected = [key] + [c for c in ("version", "state") if c in columns]
            return tuple(connection.execute("SELECT " + ",".join(selected) + " FROM " + table + " WHERE organization_id=? ORDER BY " + key, (actor.organization_id,)).fetchall())

    def audit_events(self, context, kind):
        actor = self._actor(context, "read")
        if kind not in {"admin", "access"}:
            raise ConnectorFailure(Reason.POLICY)
        with self.store.connection() as connection:
            table = "eca_admin_audit" if kind == "admin" else "eca_access_audit"
            columns = [r[1] for r in connection.execute("PRAGMA table_info(" + table + ")")]
            return tuple(dict(zip(columns, row)) for row in connection.execute("SELECT * FROM " + table + " WHERE organization_id=? ORDER BY rowid", (actor.organization_id,)))
