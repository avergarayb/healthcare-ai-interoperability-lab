"""Read a finished demonstration after a restart. Does not call a model."""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from datetime import timedelta
from pathlib import Path


def _statuses(path: Path) -> dict:
    connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    try:
        rows = connection.execute(
            "SELECT authorization_id, status FROM aip_remote_execution_reservation"
        ).fetchall()
    finally:
        connection.close()
    return {row[0]: row[1] for row in rows}


def run() -> dict:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    if os.environ.get("PLATFORM_IN_CONTAINER") != "true" or os.name != "posix":
        raise SystemExit("graph_not_in_linux")
    profile_id = os.environ.get("PLATFORM_PROFILE", "")
    from profiles import PROFILES, require_profile
    require_profile(profile_id)
    selected = PROFILES[profile_id]
    ledger_dir = Path("/var/lab/ledger") / profile_id
    live = ledger_dir / "processing.sqlite3"
    if not live.is_file():
        raise SystemExit("ledger_missing")
    before = _statuses(live)
    clinical = "pe-longitudinal-001" if profile_id.startswith("pe-") else "es-longitudinal-001"
    if before.get(clinical) != "consumed" or before.get("linux-held-001") != "held":
        raise SystemExit("reservation_rejected")

    from app.enterprise_ai_processing.execution_types import ExecutionError
    from app.enterprise_ai_processing.remote_authorization import RemoteAuthorization
    from app.enterprise_ai_processing.sqlite_ledger import SQLiteExecutionLedger
    from app.longitudinal_lab.series import OPERATION_ID, series_for
    from app.jurisdiction_lab.profile import PROFILES as JURISDICTIONS
    from tests.enterprise_ai_processing_execution_fixture import TestAccessAuthority
    from tests.enterprise_connector_fixture import Clock

    clock = Clock()
    authority = TestAccessAuthority(clock)
    ledger = SQLiteExecutionLedger(ledger_dir, authority, clock)
    try:
        executor = authority.issue(selected["organization_id"], "executor")
        try:
            ledger.consume_remote_reservation(executor, clinical)
        except ExecutionError:
            consume_reason = "denied"
        else:
            raise SystemExit("consumed_reopened")
        profile = JURISDICTIONS[profile_id]
        series = series_for(profile)
        now = clock()
        held = RemoteAuthorization(
            "linux-held-001", selected["organization_id"], "gemini-sdk-a", "gemini",
            "gemini-3.5-flash-lite", now - timedelta(minutes=1), now + timedelta(minutes=5),
            operation_id=OPERATION_ID, policy_ref=series.policy_ref,
            principal_id=executor.principal_id, resource_id="linux-held-probe",
            budget_ceiling_microusd=1000)
        decision = ledger.evaluate_remote_authorization(executor, held, 977)
        if decision.reason != "replay_denied":
            raise SystemExit("hold_released")
    finally:
        ledger.close()
    after = _statuses(live)
    if after != before:
        raise SystemExit("reservation_mutated")

    backups = sorted((Path("/var/lab/ledger") / "backup").glob("*/processing.sqlite3"))
    if not backups:
        raise SystemExit("backup_missing")
    isolated = Path("/var/lab/restore-isolated") / profile_id
    if isolated.exists():
        raise SystemExit("restore_not_isolated")
    from sqlite_backup import copy_sqlite, schema_version
    copied = copy_sqlite(backups[-1], isolated)
    restored = _statuses(copied)
    version = schema_version(copied)
    if version != 9 or restored.get(clinical) != "consumed" or restored.get("linux-held-001") != "held":
        raise SystemExit("restore_rejected")
    return {
        "outcome": "passed",
        "profile": profile_id,
        "consumed": after[clinical],
        "held": after["linux-held-001"],
        "second_consume": consume_reason,
        "held_replay": decision.reason,
        "schema_version": version,
        "restored": copied.name,
    }


def main() -> None:
    try:
        report = run()
    except SystemExit as error:
        reason = error.code if isinstance(error.code, str) else "failed"
        print(json.dumps({"outcome": "failed", "reason": reason}))
        raise SystemExit(1)
    except Exception as error:
        reason = getattr(error, "reason", None) or type(error).__name__
        print(json.dumps({"outcome": "failed", "reason": str(reason)}))
        raise SystemExit(1)
    print(json.dumps(report))


if __name__ == "__main__":
    main()
