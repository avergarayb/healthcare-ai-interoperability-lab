"""OS ownership is checked with distinct processes, never just an in-process mutex."""
import os
from pathlib import Path
import subprocess
import sys
import sqlite3

import pytest

from app.enterprise_ai_processing.execution_types import ExecutionError
from app.enterprise_ai_processing.sqlite_ledger import SQLiteExecutionLedger
from tests.enterprise_ai_processing_execution_fixture import TestAccessAuthority
from tests.enterprise_connector_fixture import Clock


CHILD = """
import sys
from app.enterprise_ai_processing.sqlite_ledger import SQLiteExecutionLedger
from app.enterprise_ai_processing.execution_types import ExecutionError
from tests.enterprise_connector_fixture import Clock
from tests.enterprise_ai_processing_execution_fixture import TestAccessAuthority
clock=Clock()
try:
    ledger=SQLiteExecutionLedger(sys.argv[1],TestAccessAuthority(clock),clock)
except ExecutionError:
    print('BLOCKED',flush=True)
    sys.exit(0)
print('OWNED',flush=True)
if len(sys.argv)>2:
    sys.stdin.readline()
ledger.close()
"""


def spawn(root, *, hold=False):
    return subprocess.Popen([sys.executable, "-B", "-c", CHILD, str(root)] + (["hold"] if hold else []),
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def test_distinct_process_cannot_own_live_file_and_close_releases(tmp_path):
    clock = Clock()
    ledger = SQLiteExecutionLedger(tmp_path, TestAccessAuthority(clock), clock)
    try:
        child = spawn(tmp_path)
        out, err = child.communicate(timeout=10)
        assert child.returncode == 0 and out.strip() == "BLOCKED" and not err
    finally:
        ledger.close()
    child = spawn(tmp_path)
    out, err = child.communicate(timeout=10)
    assert child.returncode == 0 and out.strip() == "OWNED" and not err


def test_process_death_releases_kernel_lock_not_a_pid_marker(tmp_path):
    child = spawn(tmp_path, hold=True)
    try:
        assert child.stdout.readline().strip() == "OWNED"
        child.kill()  # This exact test-owned child only; no service processes.
        child.communicate(timeout=10)
        clock = Clock()
        ledger = SQLiteExecutionLedger(tmp_path, TestAccessAuthority(clock), clock)
        ledger.close()
        assert (tmp_path / "processing.owner").exists()
    finally:
        if child.poll() is None:
            child.kill()
            child.communicate(timeout=10)


def test_second_handle_same_process_also_fails(tmp_path):
    clock = Clock()
    first = SQLiteExecutionLedger(tmp_path, TestAccessAuthority(clock), clock)
    try:
        with pytest.raises(ExecutionError):
            SQLiteExecutionLedger(tmp_path, TestAccessAuthority(clock), clock)
    finally:
        first.close()


@pytest.mark.parametrize("name", ["processing.owner", "processing.sqlite3", "processing.sqlite3-wal", "processing.sqlite3-shm", "processing.sqlite3-journal"])
def test_hard_link_alias_rejected_without_mutation(tmp_path, name):
    target = tmp_path / "other-owned-test-file"
    target.write_bytes(b"synthetic")
    os.link(target, tmp_path / name)
    clock = Clock()
    ledger = None
    try:
        with pytest.raises(ExecutionError):
            ledger = SQLiteExecutionLedger(tmp_path, TestAccessAuthority(clock), clock)
            ledger.initialize(ledger.authority.issue())
    finally:
        if ledger is not None:
            ledger.close()
    assert target.read_bytes() == b"synthetic"


def test_relative_root_rejected(tmp_path):
    clock = Clock()
    with pytest.raises(ExecutionError):
        SQLiteExecutionLedger(Path("relative-c02-root"), TestAccessAuthority(clock), clock)


@pytest.mark.parametrize("platform", ["posix", "unsupported"])
def test_unsupported_platform_fails_closed_before_creating_files(tmp_path, monkeypatch, platform):
    clock = Clock()
    with monkeypatch.context() as guard:
        # Negative gate test only: does not execute or validate POSIX locking.
        guard.setattr(os, "name", platform)
        with pytest.raises(ExecutionError):
            SQLiteExecutionLedger(tmp_path, TestAccessAuthority(clock), clock)
    assert not tuple(tmp_path.iterdir())


@pytest.mark.parametrize("nested", [False, True])
def test_native_directory_alias_cannot_acquire_coordinator(tmp_path, nested):
    assert os.name == "nt", "C02 ownership validation requires real Windows"
    import _winapi
    target, alias = tmp_path / "actual", tmp_path / "alias"
    target.mkdir()
    if nested: (target / "child").mkdir()
    # Real Windows junction, not a mock or a POSIX compatibility claim.
    _winapi.CreateJunction(str(target), str(alias))
    try:
        clock = Clock()
        root = alias / "child" if nested else alias
        with pytest.raises(ExecutionError):
            SQLiteExecutionLedger(root, TestAccessAuthority(clock), clock)
        assert not tuple(target.rglob("processing*"))
    finally:
        # Remove only the exact test-created link, never recurse into target.
        alias.rmdir()


def test_refused_close_keeps_distinct_process_blocked(tmp_path):
    from tests.enterprise_ai_processing_execution_fixture import execution_laboratory
    lab = execution_laboratory(tmp_path)
    try:
        lab.prepare()
        with pytest.raises(ExecutionError): lab.ledger.close()
        child = spawn(tmp_path)
        out, err = child.communicate(timeout=10)
        assert child.returncode == 0 and out.strip() == "BLOCKED" and not err
    finally:
        lab.close()


def test_missing_root_does_not_create_or_adopt_a_directory(tmp_path):
    root = tmp_path / "missing"
    clock = Clock()
    with pytest.raises(ExecutionError):
        SQLiteExecutionLedger(root, TestAccessAuthority(clock), clock)
    assert not root.exists()


CRASH_CHILD = """
import os,sys,socket
def denied(*args,**kwargs): raise AssertionError('offline child')
socket.socket.connect=socket.socket.connect_ex=denied
socket.getaddrinfo=socket.create_connection=denied
from tests.enterprise_ai_processing_execution_fixture import execution_laboratory
lab=execution_laboratory(sys.argv[1])
def fault(stage):
    if stage==sys.argv[2]: os._exit(71)
lab.ledger._fault=fault
lease=lab.prepare()
if sys.argv[2]=='during_fake':
    lab.gateway.model._extract=lambda owner: os._exit(71)
lab.gateway.invoke_once(lease)
os._exit(72)
"""


@pytest.mark.parametrize("stage,expected", [("T1_before_commit", None), ("T1_after_commit", "INTENT"),
    ("T2_after_commit", "CONSUMED"), ("T3_before_commit", "CONSUMED"), ("T3_after_commit", "ENTERED"),
    ("during_fake", "ENTERED"), ("T4_before_commit", "ENTERED"), ("T4_after_commit", "COMPLETED")])
def test_actual_child_process_crash_preserves_only_durable_facts(tmp_path, stage, expected):
    result = subprocess.run([sys.executable, "-B", "-c", CRASH_CHILD, str(tmp_path), stage],
        capture_output=True, text=True, timeout=15, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    assert result.returncode == 71 and not result.stdout and not result.stderr
    clock = Clock()
    authority = TestAccessAuthority(clock)
    ledger = SQLiteExecutionLedger(tmp_path, authority, clock)
    try:
        admin = authority.issue()
        ledger.initialize(admin)
        with sqlite3.connect(ledger.path) as connection:
            row = connection.execute("SELECT operation_id,run_state FROM aip_execution").fetchone()
        assert (None if row is None else row[1]) == expected
        if expected is not None and expected != "COMPLETED":
            ledger.reconcile(admin, row[0])
            with sqlite3.connect(ledger.path) as connection:
                assert connection.execute("SELECT run_state,reservation_state FROM aip_execution").fetchone() == ("UNKNOWN", "UNCERTAIN")
    finally:
        ledger.close()
