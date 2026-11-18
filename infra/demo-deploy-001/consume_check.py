"""Try to consume an already consumed permit on a backup copy."""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import timedelta
from pathlib import Path

from app.enterprise_ai_processing.execution_types import ExecutionError
from app.enterprise_ai_processing.sqlite_ledger import SQLiteExecutionLedger
from tests.enterprise_ai_processing_execution_fixture import TestAccessAuthority
from tests.enterprise_connector_fixture import Clock


def main() -> None:
    root = Path(sys.argv[1])
    path = root / "processing.sqlite3"
    authorization = sys.argv[2]
    probe = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    try:
        row = probe.execute(
            "SELECT organization_id, status FROM aip_remote_execution_reservation WHERE authorization_id=?",
            (authorization,),
        ).fetchone()
    finally:
        probe.close()
    if row is None or row[1] != "consumed":
        raise SystemExit("reservation_not_consumed")
    clock = Clock()
    authority = TestAccessAuthority(clock)
    ledger = SQLiteExecutionLedger(str(root), authority, clock)
    executor = authority.issue(row[0], "executor")
    try:
        try:
            ledger.consume_remote_reservation(executor, authorization)
            outcome = "consumed_again"
        except ExecutionError as error:
            outcome = error.reason
    finally:
        ledger.close()
    after = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    try:
        status = after.execute(
            "SELECT status FROM aip_remote_execution_reservation WHERE authorization_id=?",
            (authorization,),
        ).fetchone()[0]
    finally:
        after.close()
    report = {"authorization": authorization, "consume": outcome, "status": status}
    report["outcome"] = "passed" if outcome != "consumed_again" and status == "consumed" else "failed"
    print(json.dumps(report))
    if report["outcome"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
