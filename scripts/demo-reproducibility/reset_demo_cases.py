"""Reset disposable synthetic review rows in the local review database.

The utility deletes review state for SYN-DEMO-101 and SYN-DEMO-102 only.
It does not call FHIR, does not open the session database, does not delete
SQLite -wal or -shm files, and does not run preparation.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import re
import sqlite3
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from app.followup_review_sqlite import (
    BUSY_TIMEOUT_MS,
    SCHEMA_VERSION,
    ReviewStoreInitializationError,
    SQLiteFollowUpReviewCaseRepository,
)


REVIEW_TABLES = (
    "follow_up_review_cases",
    "follow_up_review_case_events",
    "follow_up_coordination_requests",
    "follow_up_human_attributions",
    "follow_up_coordination_request_events",
    "follow_up_review_narratives",
)
_TABLE_KEY = {
    "follow_up_review_cases": "id",
    "follow_up_review_case_events": "review_case_id",
    "follow_up_coordination_requests": "review_case_id",
    "follow_up_human_attributions": "review_case_id",
    "follow_up_coordination_request_events": "review_case_id",
    "follow_up_review_narratives": "review_case_id",
}
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class DemoResetAborted(Exception):
    """Reset stopped without committing a delete."""

    def __init__(self, reason: str, detail: str) -> None:
        self.reason = reason
        super().__init__(detail)


@dataclass(frozen=True)
class _DisposableCase:
    review_case_id: str
    case_id: str
    protocol_id: str


@dataclass(frozen=True)
class _DeletePlan:
    cases: tuple[_DisposableCase, ...]
    attribution_ids: tuple[str, ...]
    coordination_ids: tuple[str, ...]
    workflow_event_ids: tuple[str, ...]
    event_ids: tuple[str, ...]
    narrative_ids: tuple[str, ...]

    @property
    def review_case_ids(self) -> tuple[str, ...]:
        return tuple(case.review_case_id for case in self.cases)


@dataclass(frozen=True)
class DemoResetReport:
    removed_case_ids: tuple[str, ...]
    removed_attributions: int
    removed_coordination_requests: int
    removed_events: int
    removed_cases: int


def reset_demo_review(
    *,
    review_db_path: str,
    configured_review_db_path: str,
    session_db_path: str,
    knowledge_db_path: str,
    service_accepts_connections: Callable[[], bool] | None = None,
    busy_timeout_ms: int = BUSY_TIMEOUT_MS,
    after_delete_step: Callable[[str], None] | None = None,
) -> DemoResetReport:
    """Delete disposable review rows, or commit an empty reset when none exist."""
    review_path = _review_path(
        review_db_path,
        configured_review_db_path,
        session_db_path,
        knowledge_db_path,
    )
    _require_service_stopped(service_accepts_connections)
    if busy_timeout_ms < 0:
        raise DemoResetAborted(
            "exclusive_lock_unavailable",
            "exclusive review database lock was not acquired",
        )
    protocols = _approved_protocols()
    connection = sqlite3.connect(
        review_path,
        timeout=busy_timeout_ms / 1000,
        isolation_level=None,
    )
    try:
        connection.row_factory = sqlite3.Row
        connection.execute(f"PRAGMA busy_timeout={int(busy_timeout_ms)}")
        connection.execute("PRAGMA foreign_keys=ON")
        if int(connection.execute("PRAGMA foreign_keys").fetchone()[0]) != 1:
            raise DemoResetAborted(
                "referential_integrity",
                "foreign key enforcement is not active",
            )
        connection.execute("BEGIN IMMEDIATE")
        try:
            _assert_store(connection, review_path)
            plan = _plan_deletes(connection, protocols)
            preserved = _snapshot(connection, plan.review_case_ids)
            counts = _delete_disposable(connection, plan, protocols, after_delete_step)
            _assert_committed_state(connection, plan, preserved)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
    except DemoResetAborted:
        raise
    except sqlite3.OperationalError as exc:
        if "locked" in str(exc).lower():
            raise DemoResetAborted(
                "exclusive_lock_unavailable",
                "exclusive review database lock was not acquired",
            ) from exc
        raise DemoResetAborted(
            "schema_incompatible",
            "review database schema is incompatible",
        ) from exc
    finally:
        connection.close()
    return DemoResetReport(
        removed_case_ids=tuple(case.case_id for case in plan.cases),
        removed_attributions=counts["follow_up_human_attributions"],
        removed_coordination_requests=counts["follow_up_coordination_requests"],
        removed_events=counts["follow_up_review_case_events"],
        removed_cases=counts["follow_up_review_cases"],
    )


def _prepare_module():
    name = "prepare_demo_cases"
    loaded = sys.modules.get(name)
    if loaded is not None:
        return loaded
    path = Path(__file__).resolve().parent / "prepare_demo_cases.py"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise DemoResetAborted("review_db_path_invalid", "preparation controls are unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _approved_protocols() -> Mapping[str, str]:
    prepare = _prepare_module()
    return {
        prepare._POST.case_id: prepare._POST.protocol_id,
        prepare._MISSED.case_id: prepare._MISSED.protocol_id,
    }


def _review_path(
    review_db_path: str,
    configured_review_db_path: str,
    session_db_path: str,
    knowledge_db_path: str,
) -> Path:
    prepare = _prepare_module()
    try:
        return prepare._authorized_review_path(
            review_db_path,
            configured_review_db_path,
            session_db_path,
            knowledge_db_path,
        )
    except prepare.DemoPreparationAborted as exc:
        raise DemoResetAborted(exc.reason, str(exc)) from exc


def _require_service_stopped(service_accepts_connections: Callable[[], bool] | None) -> None:
    prepare = _prepare_module()
    try:
        if service_accepts_connections is None:
            accepting = prepare.tcp_accepts(prepare.SERVICE_HOST, prepare.SERVICE_PORT)
        else:
            accepting = service_accepts_connections()
    except prepare.DemoPreparationAborted as exc:
        raise DemoResetAborted(exc.reason, str(exc)) from exc
    except OSError as exc:
        raise DemoResetAborted(
            "service_check_failed",
            "Healthcare AI availability check failed",
        ) from exc
    if accepting:
        raise DemoResetAborted(
            "service_accepting_connections",
            "Healthcare AI accepts connections on 127.0.0.1:8090",
        )


def _assert_store(connection: sqlite3.Connection, review_path: Path) -> None:
    prepare = _prepare_module()
    try:
        SQLiteFollowUpReviewCaseRepository(review_path)._validate_schema(connection)
    except ReviewStoreInitializationError as exc:
        text = str(exc).lower()
        if "foreign key" in text:
            raise DemoResetAborted(
                "referential_integrity",
                "review database foreign key check failed",
            ) from exc
        raise DemoResetAborted(
            "schema_incompatible",
            "review database schema is incompatible",
        ) from exc
    version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    if version != SCHEMA_VERSION:
        raise DemoResetAborted("schema_incompatible", "review database schema is incompatible")
    names = {
        str(row[0])
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    if prepare.SESSION_TABLES & names:
        raise DemoResetAborted("session_database", "review database path is the session database")
    if prepare.KNOWLEDGE_TABLES & names:
        raise DemoResetAborted(
            "knowledge_database",
            "review database path is the institutional knowledge database",
        )
    if not set(REVIEW_TABLES).issubset(names):
        raise DemoResetAborted("schema_incompatible", "review database schema is incompatible")


def _plan_deletes(
    connection: sqlite3.Connection,
    protocols: Mapping[str, str],
) -> _DeletePlan:
    prepare = _prepare_module()
    cases = list(connection.execute("SELECT * FROM follow_up_review_cases ORDER BY id"))
    grouped: dict[str, list[sqlite3.Row]] = {}
    for row in cases:
        grouped.setdefault(str(row["case_id"]), []).append(row)
    for case_id, rows in grouped.items():
        if case_id in protocols and len(rows) > 1:
            raise DemoResetAborted(
                "ambiguous_relation",
                "disposable case id has more than one review row",
            )
        if str(case_id).startswith("SYN-DEMO-") and case_id not in protocols:
            raise DemoResetAborted(
                "ambiguous_relation",
                "unexpected disposable case id",
            )
    selected: list[_DisposableCase] = []
    for case_id, protocol_id in protocols.items():
        found = grouped.get(case_id, [])
        if not found:
            continue
        row = found[0]
        if str(row["case_id"]) in prepare.HISTORICAL_CASE_IDS:
            raise DemoResetAborted(
                "historical_case_protected",
                "historical review rows are not disposable",
            )
        if str(row["protocol_id"]) != protocol_id:
            raise DemoResetAborted(
                "review_protocol_mismatch",
                "disposable case id has a different protocol",
            )
        selected.append(
            _DisposableCase(
                review_case_id=str(row["id"]),
                case_id=str(row["case_id"]),
                protocol_id=str(row["protocol_id"]),
            )
        )
    selected_ids = {case.review_case_id for case in selected}
    if selected_ids & {str(row["id"]) for row in cases if str(row["case_id"]) in prepare.HISTORICAL_CASE_IDS}:
        raise DemoResetAborted(
            "historical_case_protected",
            "historical review rows are not disposable",
        )
    known_ids = {str(row["id"]) for row in cases}
    events = list(connection.execute("SELECT * FROM follow_up_review_case_events"))
    requests = list(connection.execute("SELECT * FROM follow_up_coordination_requests"))
    attributions = list(connection.execute("SELECT * FROM follow_up_human_attributions"))
    workflow_events = list(connection.execute("SELECT * FROM follow_up_coordination_request_events"))
    narratives = list(connection.execute("SELECT * FROM follow_up_review_narratives"))
    requests_by_id = {str(row["id"]): row for row in requests}
    events_by_case: dict[str, set[int]] = {}
    for row in events:
        events_by_case.setdefault(str(row["review_case_id"]), set()).add(int(row["case_version"]))
    _require_known_owners(events, known_ids)
    _require_known_owners(requests, known_ids)
    _require_known_owners(attributions, known_ids)
    _require_known_owners(workflow_events, known_ids)
    _require_known_owners(narratives, known_ids)
    for row in workflow_events:
        request = requests_by_id.get(str(row["coordination_request_id"]))
        if request is None or str(request["review_case_id"]) != str(row["review_case_id"]):
            raise DemoResetAborted(
                "ambiguous_relation",
                "coordination history ownership is ambiguous",
            )
    for row in attributions:
        owner = str(row["review_case_id"])
        request_id = row["coordination_request_id"]
        if request_id is not None:
            request = requests_by_id.get(str(request_id))
            if request is None or str(request["review_case_id"]) != owner:
                raise DemoResetAborted(
                    "ambiguous_relation",
                    "attribution ownership is ambiguous",
                )
        subject_version = row["subject_version"]
        if subject_version is not None and int(subject_version) not in events_by_case.get(owner, set()):
            raise DemoResetAborted(
                "ambiguous_relation",
                "attribution ownership is ambiguous",
            )
    return _DeletePlan(
        cases=tuple(selected),
        attribution_ids=tuple(
            str(row["attribution_id"]) for row in attributions if str(row["review_case_id"]) in selected_ids
        ),
        coordination_ids=tuple(
            str(row["id"]) for row in requests if str(row["review_case_id"]) in selected_ids
        ),
        workflow_event_ids=tuple(
            str(row["event_id"]) for row in workflow_events if str(row["review_case_id"]) in selected_ids
        ),
        event_ids=tuple(
            str(row["event_id"]) for row in events if str(row["review_case_id"]) in selected_ids
        ),
        narrative_ids=tuple(
            str(row["review_case_id"]) for row in narratives if str(row["review_case_id"]) in selected_ids
        ),
    )


def _require_known_owners(rows: list[sqlite3.Row], known_ids: set[str]) -> None:
    for row in rows:
        if str(row["review_case_id"]) not in known_ids:
            raise DemoResetAborted(
                "ambiguous_relation",
                "review child row has no case",
            )


def _snapshot(
    connection: sqlite3.Connection,
    excluded_case_ids: tuple[str, ...],
) -> dict[str, tuple[tuple[object, ...], ...]]:
    return {
        table: _rows(connection, table, _TABLE_KEY[table], excluded_case_ids)
        for table in REVIEW_TABLES
    }


def _rows(
    connection: sqlite3.Connection,
    table: str,
    column: str,
    excluded_case_ids: tuple[str, ...],
) -> tuple[tuple[object, ...], ...]:
    if not _IDENTIFIER.fullmatch(table) or not _IDENTIFIER.fullmatch(column):
        raise DemoResetAborted("schema_incompatible", "review database schema is incompatible")
    if excluded_case_ids:
        placeholders = ",".join("?" for _ in excluded_case_ids)
        sql = f"SELECT * FROM {table} WHERE {column} NOT IN ({placeholders}) ORDER BY 1"
        parameters = excluded_case_ids
    else:
        sql = f"SELECT * FROM {table} ORDER BY 1"
        parameters = ()
    return tuple(tuple(row) for row in connection.execute(sql, parameters))


def _delete_disposable(
    connection: sqlite3.Connection,
    plan: _DeletePlan,
    protocols: Mapping[str, str],
    after_delete_step: Callable[[str], None] | None,
) -> dict[str, int]:
    case_ids = plan.review_case_ids
    protocol_clause, protocol_params = _protocol_clause(protocols)
    steps = (
        (
            "follow_up_human_attributions",
            "attribution_id",
            plan.attribution_ids,
        ),
        (
            "follow_up_coordination_request_events",
            "event_id",
            plan.workflow_event_ids,
        ),
        (
            "follow_up_coordination_requests",
            "id",
            plan.coordination_ids,
        ),
        (
            "follow_up_review_case_events",
            "event_id",
            plan.event_ids,
        ),
        (
            "follow_up_review_narratives",
            "review_case_id",
            plan.narrative_ids,
        ),
        (
            "follow_up_review_cases",
            "id",
            case_ids,
        ),
    )
    counts: dict[str, int] = {}
    for table, key, identifiers in steps:
        counts[table] = _delete_ids(
            connection,
            table,
            key,
            identifiers,
            case_ids,
            protocol_clause,
            protocol_params,
            after_delete_step,
        )
    return counts


def _protocol_clause(protocols: Mapping[str, str]) -> tuple[str, tuple[str, ...]]:
    parts = []
    parameters: list[str] = []
    for case_id, protocol_id in protocols.items():
        parts.append("(case_id = ? AND protocol_id = ?)")
        parameters.extend((case_id, protocol_id))
    return " OR ".join(parts), tuple(parameters)


def _delete_ids(
    connection: sqlite3.Connection,
    table: str,
    key: str,
    identifiers: tuple[str, ...],
    case_ids: tuple[str, ...],
    protocol_clause: str,
    protocol_params: tuple[str, ...],
    after_delete_step: Callable[[str], None] | None,
) -> int:
    if not _IDENTIFIER.fullmatch(table) or not _IDENTIFIER.fullmatch(key):
        raise DemoResetAborted("schema_incompatible", "review database schema is incompatible")
    expected = len(identifiers)
    if expected:
        if not case_ids:
            raise DemoResetAborted(
                "ambiguous_relation",
                "disposable child rows have no case",
            )
        id_placeholders = ",".join("?" for _ in identifiers)
        case_placeholders = ",".join("?" for _ in case_ids)
        if table == "follow_up_review_cases":
            owner_sql = f"id IN ({case_placeholders}) AND ({protocol_clause})"
            owner_params: tuple[str, ...] = (*case_ids, *protocol_params)
        else:
            owner_sql = (
                f"review_case_id IN ({case_placeholders}) AND review_case_id IN ("
                f"SELECT id FROM follow_up_review_cases WHERE {protocol_clause})"
            )
            owner_params = (*case_ids, *protocol_params)
        deleted = connection.execute(
            f"DELETE FROM {table} WHERE {key} IN ({id_placeholders}) AND {owner_sql}",
            (*identifiers, *owner_params),
        ).rowcount
        if deleted != expected:
            raise DemoResetAborted(
                "delete_count_mismatch",
                "deleted row count did not match the disposable set",
            )
    if after_delete_step is not None:
        after_delete_step(table)
    return expected


def _assert_committed_state(
    connection: sqlite3.Connection,
    plan: _DeletePlan,
    preserved: dict[str, tuple[tuple[object, ...], ...]],
) -> None:
    if _check_value(connection, "PRAGMA integrity_check") != "ok":
        raise DemoResetAborted("referential_integrity", "review database integrity check failed")
    if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise DemoResetAborted("referential_integrity", "review database foreign key check failed")
    if int(_check_value(connection, "PRAGMA user_version")) != SCHEMA_VERSION:
        raise DemoResetAborted("schema_incompatible", "review database schema is incompatible")
    current = _snapshot(connection, ())
    for table in REVIEW_TABLES:
        if current[table] != preserved[table]:
            raise DemoResetAborted(
                "historical_rows_changed",
                "rows outside the disposable demonstration changed",
            )
    leftovers = connection.execute(
        """
        SELECT id FROM follow_up_review_cases
        WHERE case_id IN (?, ?)
        """,
        tuple(_approved_protocols()),
    ).fetchall()
    if leftovers:
        raise DemoResetAborted(
            "historical_rows_changed",
            "disposable review rows remained after delete",
        )
    if plan.review_case_ids:
        placeholders = ",".join("?" for _ in plan.review_case_ids)
        for table in REVIEW_TABLES[1:]:
            remaining = connection.execute(
                f"SELECT 1 FROM {table} WHERE review_case_id IN ({placeholders}) LIMIT 1",
                plan.review_case_ids,
            ).fetchone()
            if remaining is not None:
                raise DemoResetAborted(
                    "historical_rows_changed",
                    "disposable review rows remained after delete",
                )


def _check_value(connection: sqlite3.Connection, pragma: str) -> object:
    if pragma not in {"PRAGMA integrity_check", "PRAGMA user_version"}:
        raise DemoResetAborted("schema_incompatible", "review database schema is incompatible")
    return connection.execute(pragma).fetchone()[0]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reset disposable synthetic review rows.")
    parser.add_argument("--review-db", required=True)
    args = parser.parse_args(argv)
    try:
        report = reset_demo_review(
            review_db_path=args.review_db,
            configured_review_db_path=os.environ.get("AI_REVIEW_DB_PATH", ""),
            session_db_path=os.environ.get("HUMAN_SESSION_DB_PATH", ""),
            knowledge_db_path=os.environ.get("INSTITUTIONAL_KNOWLEDGE_DB_PATH", ""),
        )
    except DemoResetAborted as exc:
        print(f"{exc.reason}: {exc}", file=sys.stderr)
        return 2
    for case_id in report.removed_case_ids:
        print(f"removed {case_id}")
    print(
        "attributions="
        f"{report.removed_attributions} coordination_requests="
        f"{report.removed_coordination_requests} events="
        f"{report.removed_events} cases={report.removed_cases}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
