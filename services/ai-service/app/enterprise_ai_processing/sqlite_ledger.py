"""Explicit test-owned C02 backend. All SQLite/OS ownership stays in this module."""
from contextlib import closing, contextmanager
from dataclasses import fields
from hashlib import sha256
import os
from pathlib import Path
import sqlite3
import stat
from threading import BoundedSemaphore, RLock
from uuid import uuid4

from .execution_types import EVENTS, REASONS, TERMINAL, ExecutionError, LaboratoryAccess, identifier, instant, require, utc, uuid
from .models import AIProcessingGrant, AIProcessingPolicy, ModelProcessingProfile, ProcessingLimits, QUESTION
from ..enterprise_connectors.models import ConnectorOperation


MIGRATION = Path(__file__).parent / "migrations/001_processing_ledger.sql"
CONTRACT = "enterprise-ai-processing-ledger-v1"
AUDIT = "enterprise-ai-processing-audit-v1"


def schema_ddl(connection):
    return tuple(tuple(r) for r in connection.execute("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type,name"))


class SQLiteExecutionLedger:
    def __init__(self, root, authority, clock, *, fault=None):
        # This increment is approved/operationally tested on Windows only.
        # Reject every other platform before path, schema or ownership work.
        require(os.name == "nt", unavailable=True)
        self.root, self.authority, self.clock = Path(root), authority, clock
        self.path, self.owner_path = self.root / "processing.sqlite3", self.root / "processing.owner"
        self.barrier, self._slots = RLock(), BoundedSemaphore(4)
        self._fault = fault or (lambda stage: None)
        self._fd, self._pid, self._live = None, os.getpid(), set()
        self.process_epoch = str(uuid4())
        require(sqlite3.sqlite_version_info >= (3, 37, 0), unavailable=True)
        self._sql = MIGRATION.read_text(encoding="utf-8").replace("\r\n", "\n")
        self._checksum = sha256(self._sql.encode("utf-8")).hexdigest()
        # Schema oracle only, not storage/fallback. No runtime state lives here.
        with closing(sqlite3.connect(":memory:")) as oracle:
            oracle.executescript(self._sql)
            self._ddl = schema_ddl(oracle)
            self._execution_columns = {r[1] for r in oracle.execute("PRAGMA table_info(aip_execution)")}
        self._acquire_owner()

    def _safe(self, path, *, exists=False):
        require(self.root.is_absolute() and self.root.is_dir() and self.root == self.root.resolve(), unavailable=True)
        require(path.parent == self.root and path == path.resolve(), unavailable=True)
        for component in (path, *path.parents):
            if not component.exists() and component == path:
                require(not component.is_symlink(), unavailable=True)
                continue
            info = component.lstat()
            require(not stat.S_ISLNK(info.st_mode) and not (getattr(info, "st_file_attributes", 0) & 0x400), unavailable=True)
        if exists:
            info = path.stat()
            require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, unavailable=True)

    def _acquire_owner(self):
        fd = None
        try:
            require(os.name == "nt", unavailable=True)
            self._safe(self.owner_path)
            fd = os.open(self.owner_path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
            os.set_inheritable(fd, False)
            self._safe(self.owner_path, exists=True)
            opened, named = os.fstat(fd), self.owner_path.stat()
            require((opened.st_dev, opened.st_ino) == (named.st_dev, named.st_ino), unavailable=True)
            import msvcrt
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            self._fd, self._identity = fd, (opened.st_dev, opened.st_ino)
        except (OSError, ValueError, ExecutionError, ImportError):
            if fd is not None:
                os.close(fd)
            raise ExecutionError() from None

    def _owned(self):
        require(self._fd is not None and self._pid == os.getpid(), unavailable=True)
        self._safe(self.owner_path, exists=True)
        info = self.owner_path.stat()
        require((info.st_dev, info.st_ino) == self._identity, unavailable=True)
        for suffix in ("", "-wal", "-shm", "-journal"):
            self._safe(Path(str(self.path) + suffix), exists=Path(str(self.path) + suffix).exists())

    def close(self):
        with self.barrier:
            if self._fd is not None:
                require(not self._live, "lease_invalid")
                fd, self._fd = self._fd, None
                os.close(fd)  # Kernel releases ownership; do not unlink a live lock path.

    def _actor(self, access, roles):
        require(type(access) is LaboratoryAccess and self.authority.recognizes(access) is True, "identity_invalid")
        identifier(access.principal_id)
        identifier(access.organization_id)
        require(type(access.role) is str and access.role in roles, "scope_mismatch")
        require(instant(access.expires_at) > instant(self.clock()), "authorization_expired")
        return access

    def _validate(self, connection):
        require(schema_ddl(connection) == self._ddl, unavailable=True)
        require(connection.execute("PRAGMA quick_check(1)").fetchone()[0] == "ok", unavailable=True)
        require(connection.execute("PRAGMA foreign_key_check").fetchone() is None, unavailable=True)
        meta = connection.execute("SELECT * FROM aip_store WHERE singleton=1").fetchone()
        require(meta is not None and meta[1] == 1 and meta[2] == CONTRACT and meta[4] == self._checksum, unavailable=True)
        count, maximum = connection.execute("SELECT count(*),coalesce(max(audit_seq),0) FROM aip_audit").fetchone()
        require(count == maximum and meta[6] == maximum + 1, unavailable=True)
        count, maximum = connection.execute("SELECT count(*),coalesce(max(revision),0) FROM aip_audit WHERE event='ai_processing_policy_changed'").fetchone()
        require(count == maximum == meta[5], unavailable=True)
        for table in ("aip_profile", "aip_grant"):
            require(connection.execute("SELECT count(*) FROM " + table).fetchone()[0] <= 32, unavailable=True)
        malformed = connection.execute("SELECT count(*) FROM aip_execution WHERE "
            "(run_state IN ('INTENT','CONSUMED') AND entered_at_us IS NOT NULL) OR "
            "(run_state NOT IN ('INTENT','CONSUMED','ENTERED') AND finished_at_us IS NULL) OR "
            "(run_state='UNKNOWN' AND reservation_state='RELEASED') OR "
            "(run_state='COMPLETED' AND (result_code NOT IN ('CANDIDATE','NO_EVIDENCE') "
            "OR result_code IS NULL OR entered_at_us IS NULL OR reservation_state<>'CHARGED' "
            "OR input_units_observed IS NULL OR input_units_observed<>input_bytes "
            "OR output_units_observed IS NULL OR output_bytes_observed IS NULL "
            "OR output_units_observed>reserved_output_units OR output_bytes_observed>reserved_output_bytes))").fetchone()[0]
        require(malformed == 0, unavailable=True)

    @contextmanager
    def _transaction(self, name, *, write=True):
        # All commands, including standalone audit reads/writes, share the
        # ownership barrier. close cannot release the OS lock mid-command.
        self.barrier.acquire()
        connection = None
        acquired = False
        try:
            acquired = self._slots.acquire(timeout=0.2)
            require(acquired, unavailable=True)
            self._owned()
            self._safe(self.path, exists=True)
            connection = sqlite3.connect(self.path.as_uri() + ("?mode=rw" if write else "?mode=ro"), uri=True, timeout=0.1)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA trusted_schema=OFF")
            connection.execute("PRAGMA busy_timeout=100")
            if not write:
                connection.execute("PRAGMA query_only=ON")
            connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            self._validate(connection)
            yield connection
            if write:
                self._validate(connection)
                self._fault(name + "_before_commit")
                connection.commit()
                self._fault(name + "_after_commit")
        except ExecutionError:
            raise
        except (sqlite3.Error, OSError, ValueError, TypeError, OverflowError, KeyError):
            raise ExecutionError() from None
        finally:
            try:
                if connection is not None:
                    try:
                        connection.rollback()
                    finally:
                        connection.close()
            finally:
                if acquired:
                    self._slots.release()
                self.barrier.release()

    @staticmethod
    def _insert(connection, table, row):
        columns = tuple(row)
        connection.execute("INSERT INTO " + table + " (" + ",".join(columns) + ") VALUES ("
                           + ",".join("?" for _ in columns) + ")", tuple(row.values()))

    def _audit(self, c, event, outcome, reason="accepted", *, metadata=None, actor=None, previous=None, entity=None, subject=None):
        require(event in EVENTS and outcome in EVENTS[event][1] and reason in REASONS)
        require(sum(value is not None for value in (metadata, actor, subject)) <= 1)
        self._fault("audit_" + event)
        revision, sequence = c.execute("SELECT revision,next_audit_seq FROM aip_store").fetchone()
        row = dict(event_id=str(uuid4()), audit_seq=sequence, contract=AUDIT, timestamp_us=instant(self.clock()),
            event=event, phase=EVENTS[event][0], outcome=outcome, reason=reason,
            actor_kind="anonymous", previous_revision=revision if previous is None else previous, revision=revision)
        if actor is not None:
            row.update(actor_kind="synthetic_administrator", actor_ref=actor.principal_id, organization_id=actor.organization_id)
            if entity is not None:
                row.update(entity_kind=entity[0], entity_ref=entity[1])
        if metadata is not None:
            row.update(actor_kind="workload", actor_ref=metadata["principal_id"], organization_id=metadata["organization_id"])
            for key in ("operation_id", "decision_ref", "read_correlation_id", "instance_id", "resource_id", "grant_id",
                        "grant_version", "profile_id", "profile_version", "connector_revision"):
                row[key] = metadata[key]
            row["lease_ref"] = metadata["lease_id"]
        if subject is not None:
            row.update(actor_kind="workload", actor_ref=subject[0], organization_id=subject[1])
        self._insert(c, "aip_audit", row)
        c.execute("UPDATE aip_store SET next_audit_seq=next_audit_seq+1")

    def initialize(self, access):
        with self.barrier:
            self._actor(access, {"administrator"})
            self._owned()
            if self.path.exists():
                with self._transaction("initialize", write=False):
                    return
            try:
                with self.path.open("xb"):
                    pass
                with closing(sqlite3.connect(self.path, timeout=0.1)) as c:
                    c.execute("PRAGMA foreign_keys=ON")
                    require(c.execute("PRAGMA journal_mode=WAL").fetchone()[0].lower() == "wal", unavailable=True)
                    c.execute("BEGIN IMMEDIATE")
                    try:
                        for statement in self._sql.split(";"):
                            if statement.strip():
                                c.execute(statement)
                        c.execute("INSERT INTO aip_store VALUES (1,1,?,?,?,1,1)", (CONTRACT, str(uuid4()), self._checksum))
                        self._audit(c, "ai_processing_policy_changed", "CHANGED", actor=access, previous=0)
                        self._validate(c)
                        self._fault("initialize_before_commit")
                        c.commit()
                        self._fault("initialize_after_commit")
                    except BaseException:
                        c.rollback()
                        raise
            except (OSError, sqlite3.Error, ValueError):
                raise ExecutionError() from None

    @staticmethod
    def _encode(record):
        require(type(record) in {ModelProcessingProfile, AIProcessingGrant})
        row = {}
        for f in fields(record):
            value = getattr(record, f.name)
            if f.name == "limits":
                require(type(value) is ProcessingLimits)
                for limit in fields(value):
                    require(type(getattr(value, limit.name)) is int)
                    row[limit.name] = getattr(value, limit.name)
            elif f.name == "questions":
                require(type(value) is frozenset and value == frozenset({QUESTION}))
                row["question_set_id"] = "vacation-question-v1"
            elif f.name in {"valid_from", "expires_at", "review_due_at"}:
                row[f.name + "_us"] = instant(value)
            elif f.name == "enabled":
                require(type(value) is bool)
                row[f.name] = int(value)
            elif f.name == "read_operation":
                require(type(value) is ConnectorOperation)
                row[f.name] = value.value
            else:
                require(type(value) in {str, int} and type(value) is not bool)
                if f.name.endswith("_id"):
                    identifier(value)
                row[f.name] = value
        return row

    def change_policy(self, access, record, *, expected_revision, approval_ref=None):
        with self.barrier:
            self._actor(access, {"administrator"})
            row = self._encode(record)
            require(row["organization_id"] == access.organization_id, "scope_mismatch")
            table, key = ("aip_profile", "profile_id") if type(record) is ModelProcessingProfile else ("aip_grant", "grant_id")
            if table == "aip_grant":
                row["approval_ref"] = identifier(approval_ref)
            with self._transaction("change") as c:
                self._revision(c, expected_revision)
                old = c.execute("SELECT version FROM " + table + " WHERE organization_id=? AND " + key + "=?", (access.organization_id, row[key])).fetchone()
                require(row["version"] == (1 if old is None else old[0] + 1), "revision_conflict")
                if old is None:
                    self._insert(c, table, row)
                else:
                    values = [k for k in row if k not in {"organization_id", key}]
                    c.execute("UPDATE " + table + " SET " + ",".join(k + "=?" for k in values)
                        + " WHERE organization_id=? AND " + key + "=?", tuple(row[k] for k in values) + (access.organization_id, row[key]))
                c.execute("UPDATE aip_store SET revision=revision+1")
                self._audit(c, "ai_processing_policy_changed", "CHANGED", actor=access, previous=expected_revision,
                            entity=("profile" if table == "aip_profile" else "grant", row[key]))
            return expected_revision + 1

    @staticmethod
    def _revision(c, expected):
        require(type(expected) is int and c.execute("SELECT revision FROM aip_store").fetchone()[0] == expected,
                "revision_conflict")

    @staticmethod
    def _decode(row, cls):
        values = dict(row)
        kwargs = {}
        for f in fields(cls):
            if f.name == "limits":
                kwargs[f.name] = ProcessingLimits(**{x.name: values[x.name] for x in fields(ProcessingLimits)})
            elif f.name == "questions":
                kwargs[f.name] = frozenset({QUESTION})
            elif f.name in {"valid_from", "expires_at", "review_due_at"}:
                kwargs[f.name] = utc(values[f.name + "_us"])
            elif f.name == "enabled":
                kwargs[f.name] = bool(values[f.name])
            elif f.name == "read_operation":
                kwargs[f.name] = ConnectorOperation(values[f.name])
            else:
                kwargs[f.name] = values[f.name]
        return cls(**kwargs)

    def policy(self, access):
        self._actor(access, {"executor", "administrator"})
        with self._transaction("policy", write=False) as c:
            revision = c.execute("SELECT revision FROM aip_store").fetchone()[0]
            profiles = tuple(self._decode(r, ModelProcessingProfile) for r in c.execute("SELECT * FROM aip_profile WHERE organization_id=? ORDER BY profile_id", (access.organization_id,)))
            grants = tuple(self._decode(r, AIProcessingGrant) for r in c.execute("SELECT * FROM aip_grant WHERE organization_id=? ORDER BY grant_id", (access.organization_id,)))
            return AIProcessingPolicy(revision, grants, profiles)

    def approval_ref(self, access, grant_id, version, revision):
        self._actor(access, {"executor"})
        identifier(grant_id)
        with self._transaction("approval", write=False) as c:
            self._revision(c, revision)
            row = c.execute("SELECT approval_ref,version FROM aip_grant WHERE organization_id=? AND grant_id=?",
                            (access.organization_id, grant_id)).fetchone()
            require(row is not None and row[1] == version, "policy_changed")
            return row[0]

    def _command(self, access, metadata):
        self._actor(access, {"executor"})
        require(type(metadata) is dict)
        expected = self._execution_columns - {"consumed_at_us", "entered_at_us", "finished_at_us", "lease_state", "run_state",
            "reservation_state", "result_code", "input_units_observed", "output_bytes_observed", "output_units_observed", "elapsed_us"}
        require(set(metadata) == expected)
        require(metadata["organization_id"] == access.organization_id, "scope_mismatch")
        for key, value in metadata.items():
            if key in {"operation_id", "owner_ref", "process_epoch", "lease_id", "decision_ref", "read_correlation_id"}:
                uuid(value)
            elif key.endswith(("_id", "_ref")):
                identifier(value)
            elif key in {"principal_type", "destination", "classification", "read_operation", "read_purpose",
                         "processing_operation", "processing_purpose"}:
                require(type(value) is str)
            else:
                require(type(value) is int)
        require(metadata["process_epoch"] == self.process_epoch, "lease_invalid")

    def reserve(self, access, metadata):
        self._command(access, metadata)
        with self._transaction("T1") as c:
            self._revision(c, metadata["processing_revision"])
            require(instant(self.clock()) < metadata["expires_at_us"], "authorization_expired")
            require(c.execute("SELECT 1 FROM aip_execution WHERE organization_id=? AND instance_id=? AND profile_id=? AND reservation_state IN ('HELD','UNCERTAIN')",
                (access.organization_id, metadata["instance_id"], metadata["profile_id"])).fetchone() is None, "budget_exceeded")
            require(c.execute("SELECT 1 FROM aip_execution WHERE (organization_id=? AND operation_id=?) OR lease_id=?",
                (access.organization_id, metadata["operation_id"], metadata["lease_id"])).fetchone() is None, "lease_invalid")
            grant = c.execute("SELECT * FROM aip_grant WHERE organization_id=? AND grant_id=?", (access.organization_id, metadata["grant_id"])).fetchone()
            profile = c.execute("SELECT * FROM aip_profile WHERE organization_id=? AND profile_id=?", (access.organization_id, metadata["profile_id"])).fetchone()
            require(grant is not None and profile is not None and grant["enabled"] and profile["enabled"], "processing_not_granted")
            require(grant["version"] == metadata["grant_version"] and profile["version"] == metadata["profile_version"], "policy_changed")
            require(grant["profile_version"] == profile["version"] and grant["approval_ref"] == metadata["approval_ref"], "policy_changed")
            row = dict(metadata, lease_state="ISSUED", run_state="INTENT", reservation_state="HELD")
            self._insert(c, "aip_execution", row)
            for event, outcome in (("ai_processing_evaluated", "ALLOW"), ("ai_processing_profile_selected", "ALLOW"),
                                   ("ai_processing_budget_approved", "ALLOW"), ("ai_processing_authorized", "AUTHORIZED")):
                self._audit(c, event, outcome, metadata=metadata)
            self._live.add((access.organization_id, metadata["operation_id"]))

    def _attempt(self, c, access, metadata, version):
        row = c.execute("SELECT * FROM aip_execution WHERE organization_id=? AND operation_id=?", (access.organization_id, metadata["operation_id"])).fetchone()
        require(row is not None and type(version) is int and row["attempt_version"] == version, "lease_invalid")
        require(all(row[k] == v for k, v in metadata.items() if k != "attempt_version"), "lease_invalid")
        return row

    def _advance(self, access, metadata, version, before, after, name):
        self._command(access, metadata)
        with self._transaction(name) as c:
            row = self._attempt(c, access, metadata, version)
            self._revision(c, metadata["processing_revision"])
            require(row["run_state"] == before, "lease_invalid")
            now = instant(self.clock())
            require(now < row["expires_at_us"], "authorization_expired")
            stamp = "consumed_at_us" if after == "CONSUMED" else "entered_at_us"
            changed = c.execute("UPDATE aip_execution SET run_state=?,lease_state='CONSUMED'," + stamp + "=?,attempt_version=attempt_version+1 WHERE organization_id=? AND operation_id=? AND attempt_version=?",
                (after, now, access.organization_id, metadata["operation_id"], version))
            require(changed.rowcount == 1, "lease_invalid")
            self._audit(c, "ai_processing_evaluated" if after == "CONSUMED" else "ai_provider_invocation_observed",
                        "ALLOW" if after == "CONSUMED" else "OBSERVED", metadata=metadata)
        return version + 1

    def consume(self, access, metadata, version):
        return self._advance(access, metadata, version, "INTENT", "CONSUMED", "T2")

    def observe_entry(self, access, metadata, version):
        return self._advance(access, metadata, version, "CONSUMED", "ENTERED", "T3")

    def finish(self, access, metadata, version, state, reason, reservation, usage):
        self._command(access, metadata)
        require(state in TERMINAL and reservation in {"RELEASED", "CHARGED", "UNCERTAIN"})
        require(type(usage) is dict and set(usage) == {"input_units", "output_bytes", "output_units", "elapsed_us", "result_code"})
        require(type(state) is str and type(reservation) is str and type(usage["result_code"]) is str)
        require(state != "UNKNOWN" or (reservation == "UNCERTAIN" and usage["result_code"] == "UNKNOWN"))
        for key, maximum in (("input_units", 2048), ("output_bytes", 1000000), ("output_units", 1000000),
                             ("elapsed_us", 9223372036854775807)):
            require(type(usage[key]) is int and 0 <= usage[key] <= maximum)
        with self._transaction("T4") as c:
            row = self._attempt(c, access, metadata, version)
            require(row["run_state"] not in TERMINAL, "lease_invalid")
            require(reservation != "RELEASED" or row["entered_at_us"] is None, "lease_invalid")
            if state == "COMPLETED":
                self._revision(c, metadata["processing_revision"])
                require(row["run_state"] == "ENTERED" and reservation == "CHARGED")
                require(usage["result_code"] in {"CANDIDATE", "NO_EVIDENCE"})
                require(usage["input_units"] == row["input_bytes"] and usage["output_bytes"] <= row["reserved_output_bytes"]
                        and usage["output_units"] <= row["reserved_output_units"], "budget_exceeded")
            lease_state = state if state in {"EXPIRED", "REVOKED"} else "CLOSED"
            changed = c.execute("UPDATE aip_execution SET run_state=?,lease_state=?,reservation_state=?,finished_at_us=?,attempt_version=attempt_version+1,input_units_observed=?,output_bytes_observed=?,output_units_observed=?,elapsed_us=?,result_code=? WHERE organization_id=? AND operation_id=? AND attempt_version=?",
                (state, lease_state, reservation, instant(self.clock()), usage["input_units"], usage["output_bytes"],
                 usage["output_units"], usage["elapsed_us"], usage["result_code"], access.organization_id, metadata["operation_id"], version))
            require(changed.rowcount == 1, "lease_invalid")
            self._audit(c, "ai_processing_evaluated", "ALLOW" if state == "COMPLETED" else "DENY", reason, metadata=metadata)
            if row["entered_at_us"] is not None and usage["result_code"] in {"CANDIDATE", "NO_EVIDENCE", "INVALID"}:
                self._audit(c, "ai_provider_result_observed", "UNKNOWN" if state == "UNKNOWN" else "OBSERVED", reason, metadata=metadata)
            if state != "COMPLETED":
                event, outcome = (("ai_processing_cancelled", "CANCELLED") if state == "CANCELLED" else
                    (("ai_processing_revocation_detected", "REVOKED") if state in {"REVOKED", "EXPIRED"} else ("ai_processing_error", "ERROR")))
                self._audit(c, event, outcome, reason, metadata=metadata)
        self._live.discard((access.organization_id, metadata["operation_id"]))

    def retire_runtime(self, access, metadata):
        # Cleanup must still retire this process's record after authority expiry.
        with self.barrier:
            require(type(access) is LaboratoryAccess and self.authority.recognizes(access) is True
                    and access.role == "executor" and access.organization_id == metadata["organization_id"], "identity_invalid")
            self._live.discard((access.organization_id, metadata["operation_id"]))

    def deny(self, reason, *, unavailable=False, access=None, subject=None):
        require((access is None) == (subject is None))
        if access is not None:
            self._actor(access, {"executor"})
            require(type(subject) is tuple and len(subject) == 2)
            identifier(subject[0])
            identifier(subject[1])
            require(subject[1] == access.organization_id, "scope_mismatch")
        with self._transaction("deny") as c:
            self._audit(c, "ai_processing_evaluated", "UNAVAILABLE" if unavailable else "DENY", reason, subject=subject)

    def read_audit(self, access, *, cursor=0, limit=100):
        self._actor(access, {"administrator", "auditor"})
        require(type(cursor) is int and 0 <= cursor <= 1000000 and type(limit) is int and 1 <= limit <= 100)
        with self._transaction("read_audit", write=False) as c:
            return tuple({k: row[k] for k in row.keys() if k != "audit_seq"} for row in c.execute(
                "SELECT * FROM aip_audit WHERE organization_id=? ORDER BY audit_seq LIMIT ? OFFSET ?",
                (access.organization_id, limit, cursor)))

    def reconcile(self, access, operation_id, *, release_slot=False):
        with self.barrier:
            self._actor(access, {"administrator"})
            require(type(release_slot) is bool)
            uuid(operation_id)
            require((access.organization_id, operation_id) not in self._live, "lease_invalid")
            with self._transaction("reconcile") as c:
                row = c.execute("SELECT * FROM aip_execution WHERE organization_id=? AND operation_id=?", (access.organization_id, operation_id)).fetchone()
                require(row is not None and (row["run_state"] in {"INTENT", "CONSUMED", "ENTERED", "UNKNOWN"}), "lease_invalid")
                reservation = "CHARGED" if release_slot else "UNCERTAIN"
                c.execute("UPDATE aip_execution SET run_state='UNKNOWN',lease_state='CLOSED',reservation_state=?,finished_at_us=?,result_code='UNKNOWN',attempt_version=attempt_version+1 WHERE organization_id=? AND operation_id=?",
                    (reservation, instant(self.clock()), access.organization_id, operation_id))
                self._audit(c, "ai_processing_error", "UNKNOWN", "execution_unknown", actor=access,
                            entity=("execution", operation_id))
