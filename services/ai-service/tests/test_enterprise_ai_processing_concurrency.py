"""Deterministic barriers/Events: local laboratory guarantees, not Graph revocation."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from app.enterprise_ai_processing.execution_types import ExecutionError, ExecutionOwner
from tests.enterprise_ai_processing_execution_fixture import execution_laboratory


@pytest.fixture
def lab(tmp_path):
    instance = execution_laboratory(tmp_path)
    try:
        yield instance
    finally:
        instance.close()


def test_two_consumers_of_same_original_lease_start_only_once(lab, monkeypatch):
    lease = lab.prepare()
    entered, resume = Event(), Event()
    extract = lab.gateway.model._extract
    def paused(owner):
        try:
            entered.set()
            assert resume.wait(5)
            extract(owner)
        finally:
            owner = None
    monkeypatch.setattr(lab.gateway.model, "_extract", paused)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(lab.gateway.invoke_once, lease)
        try:
            assert entered.wait(5)
            second = pool.submit(lab.gateway.invoke_once, lease).result(timeout=5)
            assert second.state == "DENY" and second.entries == 0
        finally:
            resume.set()
        assert first.result(timeout=5).state == "COMPLETED"


def test_commit_from_independent_connection_during_fake_and_revoke(lab, monkeypatch):
    lease = lab.prepare()
    entered, resume = Event(), Event()
    extract = lab.gateway.model._extract
    def paused(owner):
        try:
            entered.set()
            assert resume.wait(5)
            extract(owner)
        finally:
            owner = None
    monkeypatch.setattr(lab.gateway.model, "_extract", paused)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(lab.gateway.invoke_once, lease)
        try:
            assert entered.wait(5)
            # Every ledger command opens its own connection; this commit must
            # finish while the fake is paused, not after releasing resume.
            revision = lab.change_grant(enabled=False)
            assert revision == 6 and not resume.is_set()
        finally:
            resume.set()
        result = future.result(timeout=5)
    assert result.state == "REVOKED" and result.entries == result.processing_started == 1


@pytest.mark.parametrize("secondary", ["none", "retire", "clear", "both"])
def test_cancellation_of_a_does_not_clear_b(lab, monkeypatch, secondary):
    first, second = lab.prepare(), lab.prepare("b")
    owner_a, owner_b = lab.gateway._owners[id(first)], lab.gateway._owners[id(second)]
    ready_b, resume_b = Event(), Event()
    primary = asyncio.CancelledError("synthetic A cancellation")
    retire, clear = lab.ledger.retire_runtime, ExecutionOwner.clear
    def retire_one(access, metadata):
        if metadata["organization_id"] == "ORG-A": raise RuntimeError("synthetic retire failure")
        retire(access, metadata)
    def clear_one(owner):
        try:
            if owner is owner_a: raise RuntimeError("synthetic clear failure")
            clear(owner)
        finally:
            owner = None
    if secondary in {"retire", "both"}: monkeypatch.setattr(lab.ledger, "retire_runtime", retire_one)
    if secondary in {"clear", "both"}: monkeypatch.setattr(ExecutionOwner, "clear", clear_one)
    extract = lab.gateway.model._extract
    def controlled(owner):
        try:
            if owner.metadata["organization_id"] == "ORG-A":
                assert ready_b.wait(5)
                raise primary
            ready_b.set()
            assert resume_b.wait(5)
            extract(owner)
        finally:
            owner = None
    monkeypatch.setattr(lab.gateway.model, "_extract", controlled)
    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(lab.gateway.invoke_once, first)
        b = pool.submit(lab.gateway.invoke_once, second)
        try:
            with pytest.raises(asyncio.CancelledError) as caught:
                a.result(timeout=5)
            assert caught.value is primary and owner_a.done
            assert not owner_b.done and owner_b.input_bytes is not None
        finally:
            resume_b.set()
        assert b.result(timeout=5).state == "COMPLETED"


def test_coordinated_writer_is_not_confirmed_inside_admission(lab, monkeypatch):
    lease = lab.prepare()
    at_consume, tried, allow_entry, written = Event(), Event(), Event(), Event()
    extract = lab.gateway.model._extract
    def fault(stage):
        if stage == "T2_after_commit":
            at_consume.set()
            assert tried.wait(5)
            assert allow_entry.wait(5)
    def writer():
        assert at_consume.wait(5)
        acquired = lab.ledger.barrier.acquire(blocking=False)
        assert not acquired
        tried.set()
        lab.change_grant(enabled=False)
        written.set()
    def processing(owner):
        try:
            assert written.wait(5)
            extract(owner)
        finally:
            owner = None
    lab.ledger._fault = fault
    monkeypatch.setattr(lab.gateway.model, "_extract", processing)
    with ThreadPoolExecutor(max_workers=2) as pool:
        execution = pool.submit(lab.gateway.invoke_once, lease)
        writer_future = pool.submit(writer)
        try:
            assert tried.wait(5) and not written.is_set()
        finally:
            allow_entry.set()
        writer_future.result(timeout=5)
        result = execution.result(timeout=5)
    assert result.entries == 1 and result.state == "REVOKED"


def test_uncoordinated_change_between_last_check_and_processing_is_a_limit(lab, monkeypatch):
    lease = lab.prepare()
    seal = lab.gateway._seal
    changed = []
    def gap(owner):
        try:
            seal(owner)
            if owner.entries == 1 and not changed:
                # Explicitly violates the fixture admission protocol. Physical
                # adapter entry has happened; computational processing has not.
                lab.connector.adapter.set_permission(("ORG-A", "instance-a", "vacation-a"), False)
                changed.append(True)
        finally:
            owner = None
    monkeypatch.setattr(lab.gateway, "_seal", gap)
    result = lab.gateway.invoke_once(lease)
    assert changed and result.entries == result.processing_started == 1 and result.state == "REVOKED"
    # This test documents the gap; it is NOT a PASS for global/live revocation.


def test_close_during_processing_does_not_release_ownership_or_clear_owner(lab, monkeypatch):
    lease = lab.prepare()
    owner = lab.gateway._owners[id(lease)]
    entered, resume = Event(), Event()
    extract = lab.gateway.model._extract
    def paused(current):
        try:
            entered.set()
            assert resume.wait(5)
            extract(current)
        finally:
            current = None
    monkeypatch.setattr(lab.gateway.model, "_extract", paused)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(lab.gateway.invoke_once, lease)
        try:
            assert entered.wait(5)
            with pytest.raises(ExecutionError): lab.close()
            assert lab.ledger._fd is not None and not owner.done and owner.input_bytes is not None
        finally:
            resume.set()
        assert future.result(timeout=5).state == "COMPLETED"
