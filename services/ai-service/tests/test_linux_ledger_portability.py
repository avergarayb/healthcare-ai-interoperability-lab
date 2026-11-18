"""Process-level reservation checks for the portable ledger lock.

Threads are not enough. Each child is a separate interpreter. The owner lock
lets only one of them open the ledger. The durable row, not a restart, decides
whether a permit can be used again.
"""
import os
from pathlib import Path
import subprocess
import sys

import pytest

from app.enterprise_llm_providers.errors import ProviderError
from app.enterprise_llm_providers.transport import live_egress_enabled
from app.longitudinal_lab.policy import request_real_provider_send
from tests.test_lab_summary import _open_clinical, _permit
from tests.test_model_gateway_durable_authorization import _ready


AUTH = "linux-permit-a"
CHILD = r"""
import os, sys
from datetime import timedelta
from app.enterprise_ai_processing.execution_types import ExecutionError
from app.enterprise_ai_processing.remote_authorization import (
    CLINICAL_OPERATION_ID, CLINICAL_POLICY_REF, RemoteAuthorization)
from app.enterprise_ai_processing.sqlite_ledger import SQLiteExecutionLedger
from tests.enterprise_ai_processing_execution_fixture import TestAccessAuthority
from tests.enterprise_connector_fixture import Clock

def crash(stage):
    if stage == os.environ.get("CRASH_STAGE", ""):
        os._exit(91)

clock = Clock()
authority = TestAccessAuthority(clock)
try:
    ledger = SQLiteExecutionLedger(sys.argv[1], authority, clock, fault=crash)
except ExecutionError:
    print("BLOCKED", flush=True)
    raise SystemExit(0)
executor = authority.issue("ORG-A", "executor")
now = clock()
record = RemoteAuthorization(
    "linux-permit-a", "ORG-A", "gemini-sdk-a", "gemini", "gemini-3.5-flash-lite",
    now - timedelta(minutes=1), now + timedelta(minutes=5),
    operation_id=CLINICAL_OPERATION_ID, policy_ref=CLINICAL_POLICY_REF,
    principal_id=executor.principal_id, resource_id="MHS-PAT-001",
    budget_ceiling_microusd=1000)
action = sys.argv[2]
try:
    if action == "reserve":
        decision = ledger.evaluate_remote_authorization(executor, record, int(sys.argv[3]))
        print("DECISION %s %s" % (decision.allowed, decision.reason), flush=True)
        if "hold" in sys.argv:
            sys.stdin.readline()
    elif action == "consume":
        try:
            ledger.consume_remote_reservation(executor, "linux-permit-a")
            print("CONSUMED", flush=True)
        except ExecutionError as error:
            print("CONSUME %s" % error.reason, flush=True)
    elif action == "audit":
        with ledger._transaction("audit", write=False) as connection:
            rows = connection.execute(
                "SELECT status FROM aip_remote_execution_reservation WHERE authorization_id=?",
                ("linux-permit-a",)).fetchall()
            allows = connection.execute(
                "SELECT count(*) FROM aip_remote_authorization_audit "
                "WHERE authorization_id=? AND event='remote_authorization_evaluated' "
                "AND outcome='ALLOW' AND reason='accepted'",
                ("linux-permit-a",)).fetchone()[0]
            permit = connection.execute(
                "SELECT status FROM aip_remote_execution_permit WHERE authorization_id=?",
                ("linux-permit-a",)).fetchone()
        status = "none" if not rows else ",".join(row["status"] for row in rows)
        print("AUDIT %s %s %s" % (status, allows, permit["status"]), flush=True)
finally:
    ledger.close()
"""


def _spawn(root, action, *args, env=None):
    child_env = os.environ.copy()
    child_env.pop("GEMINI_API_KEY", None)
    child_env.pop("OPENAI_API_KEY", None)
    if env:
        child_env.update(env)
    return subprocess.Popen(
        [sys.executable, "-B", "-c", CHILD, str(root), action, *args],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        env=child_env, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def _prepared(tmp_path):
    lab = _ready(tmp_path)
    _open_clinical(lab)
    _permit(lab, AUTH, budget_ceiling_microusd=1000)
    lab.close()
    return tmp_path


def _line(child):
    line = child.stdout.readline().strip()
    if child.poll() not in (None, 0) and not line:
        raise AssertionError(child.stderr.read())
    return line


def test_wal_full_synchronous_stays_durable(tmp_path):
    lab = _ready(tmp_path)
    try:
        with lab.ledger._transaction("durability") as connection:
            journal = connection.execute("PRAGMA journal_mode").fetchone()[0]
            sync = connection.execute("PRAGMA synchronous").fetchone()[0]
        assert str(journal).lower() == "wal"
        assert int(sync) == 2
    finally:
        lab.close()


def test_two_processes_reserve_once_and_a_late_process_is_denied(tmp_path):
    root = _prepared(tmp_path)
    first, second = _spawn(root, "reserve", "977", "hold"), _spawn(root, "reserve", "977", "hold")
    try:
        lines = sorted([_line(first), _line(second)])
        assert lines == ["BLOCKED", "DECISION True accepted"]
    finally:
        for child in (first, second):
            if child.poll() is None:
                child.stdin.write("\n")
                child.stdin.flush()
                child.communicate(timeout=10)
    owner = _spawn(root, "audit")
    out, err = owner.communicate(timeout=10)
    assert owner.returncode == 0 and out.strip() == "AUDIT held 1 active" and not err
    late = _spawn(root, "reserve", "977")
    out, err = late.communicate(timeout=10)
    assert late.returncode == 0 and out.strip() == "DECISION False replay_denied" and not err
    again = _spawn(root, "reserve", "977")
    out, err = again.communicate(timeout=10)
    assert again.returncode == 0 and out.strip() == "DECISION False replay_denied" and not err


def test_budget_above_the_ceiling_inserts_nothing(tmp_path):
    root = _prepared(tmp_path)
    child = _spawn(root, "reserve", "1001")
    out, err = child.communicate(timeout=10)
    assert child.returncode == 0 and out.strip() == "DECISION False budget_exceeded" and not err
    audit = _spawn(root, "audit")
    out, err = audit.communicate(timeout=10)
    assert audit.returncode == 0 and out.strip() == "AUDIT none 0 active" and not err


def test_consumed_permit_stays_consumed_for_a_later_process(tmp_path):
    root = _prepared(tmp_path)
    hold = _spawn(root, "reserve", "977")
    out, err = hold.communicate(timeout=10)
    assert hold.returncode == 0 and out.strip() == "DECISION True accepted" and not err
    first = _spawn(root, "consume")
    out, err = first.communicate(timeout=10)
    assert first.returncode == 0 and out.strip() == "CONSUMED" and not err
    second = _spawn(root, "consume")
    out, err = second.communicate(timeout=10)
    assert second.returncode == 0 and out.strip() == "CONSUME internal_failure" and not err
    third = _spawn(root, "reserve", "977")
    out, err = third.communicate(timeout=10)
    assert third.returncode == 0 and out.strip() == "DECISION False replay_denied" and not err
    audit = _spawn(root, "audit")
    out, err = audit.communicate(timeout=10)
    assert audit.returncode == 0 and out.strip() == "AUDIT consumed 1 active" and not err


def test_held_reservation_survives_process_death(tmp_path):
    root = _prepared(tmp_path)
    child = _spawn(root, "reserve", "977", "hold")
    try:
        assert _line(child) == "DECISION True accepted"
        child.kill()
        child.communicate(timeout=10)
    finally:
        if child.poll() is None:
            child.kill()
            child.communicate(timeout=10)
    audit = _spawn(root, "audit")
    out, err = audit.communicate(timeout=10)
    assert audit.returncode == 0 and out.strip() == "AUDIT held 1 active" and not err
    late = _spawn(root, "reserve", "977")
    out, err = late.communicate(timeout=10)
    assert late.returncode == 0 and out.strip() == "DECISION False replay_denied" and not err


def test_crash_during_the_reservation_transaction_keeps_the_prior_row(tmp_path):
    root = _prepared(tmp_path)
    child = _spawn(root, "reserve", "977", env={"CRASH_STAGE": "reserve_before_insert"})
    out, err = child.communicate(timeout=10)
    assert child.returncode == 91 and out == "" and not err
    audit = _spawn(root, "audit")
    out, err = audit.communicate(timeout=10)
    assert audit.returncode == 0 and out.strip() == "AUDIT none 0 active" and not err
    recovered = _spawn(root, "reserve", "977")
    out, err = recovered.communicate(timeout=10)
    assert recovered.returncode == 0 and out.strip() == "DECISION True accepted" and not err


def test_second_open_does_not_drop_the_live_owner(tmp_path):
    from app.enterprise_ai_processing.execution_types import ExecutionError
    from app.enterprise_ai_processing.sqlite_ledger import SQLiteExecutionLedger
    from tests.enterprise_ai_processing_execution_fixture import TestAccessAuthority
    from tests.enterprise_connector_fixture import Clock

    clock = Clock()
    owner = SQLiteExecutionLedger(tmp_path, TestAccessAuthority(clock), clock)
    try:
        with pytest.raises(ExecutionError):
            SQLiteExecutionLedger(tmp_path, TestAccessAuthority(clock), clock)
        child = _spawn(tmp_path, "audit")
        out, err = child.communicate(timeout=10)
        assert child.returncode == 0 and out.strip() == "BLOCKED" and not err
    finally:
        owner.close()


def test_an_accidental_provider_key_does_not_open_a_send(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "synthetic-not-a-real-key")
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-not-a-real-key")
    assert live_egress_enabled() is False
    with pytest.raises(ProviderError) as caught:
        request_real_provider_send()
    assert caught.value.reason == "provider_send_blocked"


def test_posix_without_a_lock_primitive_fails_before_creating_files(tmp_path, monkeypatch):
    if os.name == "posix":
        pytest.skip("this interpreter has fcntl")
    from app.enterprise_ai_processing.execution_types import ExecutionError
    from app.enterprise_ai_processing.sqlite_ledger import SQLiteExecutionLedger
    from tests.enterprise_ai_processing_execution_fixture import TestAccessAuthority
    from tests.enterprise_connector_fixture import Clock

    clock = Clock()
    monkeypatch.setattr(os, "name", "posix")
    with pytest.raises(ExecutionError):
        SQLiteExecutionLedger(tmp_path, TestAccessAuthority(clock), clock)
    assert not tuple(Path(tmp_path).iterdir())
