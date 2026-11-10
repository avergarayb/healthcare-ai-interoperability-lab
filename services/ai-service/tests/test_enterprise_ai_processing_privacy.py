"""Bounded read-only traceback diagnostics; no runtime frame scrubbing."""
import asyncio
import logging
import sqlite3
import traceback

import pytest

from app.enterprise_ai_processing.execution_types import ExecutionOwner
from tests.enterprise_ai_processing_execution_fixture import execution_laboratory


CANARY = "C02_PRIVATE_SYNTHETIC_CANARY_7f2"


@pytest.fixture
def lab(tmp_path):
    instance = execution_laboratory(tmp_path, text="VACACIONES: 37 dias tras 15 meses de servicio. " + CANARY)
    try:
        yield instance
    finally:
        instance.close()


@pytest.mark.parametrize("signal", [KeyboardInterrupt, asyncio.CancelledError])
@pytest.mark.parametrize("secondary", ["none", "retire", "clear", "both"])
def test_retained_cancellation_traceback_has_no_owned_payload(lab, monkeypatch, signal, secondary):
    lease = lab.prepare()
    owner = lab.gateway._owners[id(lease)]
    primary = signal("synthetic cancellation")
    def interrupt(current):
        try:
            raise primary
        finally:
            current = None
    def fail(*args):
        raise RuntimeError("synthetic secondary cleanup failure")
    monkeypatch.setattr(lab.gateway.model, "_extract", interrupt)
    if secondary in {"retire", "both"}: monkeypatch.setattr(lab.ledger, "retire_runtime", fail)
    if secondary in {"clear", "both"}: monkeypatch.setattr(ExecutionOwner, "clear", fail)
    with pytest.raises(signal) as caught:
        lab.gateway.invoke_once(lease)
    assert caught.value is primary
    assert owner.done and owner.source_bytes is owner.question_bytes is owner.input_bytes is owner.candidate is None
    assert owner.envelope is owner.original_source is owner.original_input is None
    snapshot = traceback.TracebackException.from_exception(primary, capture_locals=True)
    for frame in snapshot.stack:
        if "app" in frame.filename and "enterprise_ai_processing" in frame.filename:
            assert CANARY not in repr(frame.locals)
    assert not lab.gateway._owners


@pytest.mark.parametrize("chain", ["cause", "context", "group"])
def test_error_chains_do_not_escape_as_payload_or_keep_owner(lab, monkeypatch, chain):
    lease = lab.prepare()
    owner = lab.gateway._owners[id(lease)]
    captured = []
    def fail(current):
        try:
            try:
                raise ValueError("synthetic inner")
            except ValueError as error:
                if chain == "cause": raise RuntimeError("synthetic outer") from error
                if chain == "group": raise ExceptionGroup("synthetic group", [error])
                raise RuntimeError("synthetic context")
        except Exception as error:
            captured.append(error)
            raise
        finally:
            current = None
    monkeypatch.setattr(lab.gateway.model, "_extract", fail)
    assert lab.gateway.invoke_once(lease).state == "UNAVAILABLE"
    assert owner.done and owner.input_bytes is owner.envelope is None
    assert captured
    for error in captured:
        snapshot = traceback.TracebackException.from_exception(error, capture_locals=True)
        for frame in snapshot.stack:
            if "app" in frame.filename and "enterprise_ai_processing" in frame.filename:
                assert CANARY not in repr(frame.locals)


def test_sqlite_files_audit_repr_and_logs_do_not_contain_canary(lab, caplog):
    with caplog.at_level(logging.DEBUG):
        lease = lab.prepare()
        owner = lab.gateway._owners[id(lease)]
        assert CANARY not in repr(owner) and CANARY not in repr(lease)
        result = lab.gateway.invoke_once(lease)
    assert result.state == "COMPLETED" and CANARY not in repr(result)
    assert CANARY not in caplog.text
    assert CANARY not in repr(lab.ledger.read_audit(lab.admin["ORG-A"]))
    lab.close()  # Windows deliberately denies reads of the OS-locked owner byte.
    for path in lab.ledger.root.glob("processing*"):
        assert CANARY.encode() not in path.read_bytes()


def test_primary_cancel_survives_secondary_interrupt_during_finalization(lab, monkeypatch):
    lease = lab.prepare()
    primary = asyncio.CancelledError("primary synthetic signal")
    def cancel(owner):
        try:
            raise primary
        finally:
            owner = None
    def secondary(*args, **kwargs):
        raise KeyboardInterrupt("secondary synthetic signal")
    monkeypatch.setattr(lab.gateway.model, "_extract", cancel)
    monkeypatch.setattr(lab.ledger, "finish", secondary)
    with pytest.raises(asyncio.CancelledError) as caught:
        lab.gateway.invoke_once(lease)
    assert caught.value is primary


def test_live_wal_and_database_do_not_contain_owned_input(lab):
    # A test-only observer pins a snapshot so WAL survives writer connection
    # close. The gateway still holds no transaction while processing the fake.
    observer = sqlite3.connect(lab.ledger.path)
    try:
        observer.execute("BEGIN")
        observer.execute("SELECT count(*) FROM aip_audit").fetchone()
        assert lab.gateway.invoke_once(lab.prepare()).state == "COMPLETED"
        wal = lab.ledger.path.with_name(lab.ledger.path.name + "-wal")
        assert wal.is_file() and wal.stat().st_size > 0
        assert CANARY.encode() not in wal.read_bytes()
        assert CANARY.encode() not in lab.ledger.path.read_bytes()
    finally:
        observer.rollback()
        observer.close()
