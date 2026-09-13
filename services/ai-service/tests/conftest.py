from __future__ import annotations

import copy
from typing import Any

import pytest

from app.config import Settings


def collection(*, retained_count: int) -> dict[str, Any]:
    return {
        "status": "SUCCESS",
        "receivedCount": retained_count,
        "retainedCount": retained_count,
        "truncated": False,
        "records": [],
    }


def contract(
    *,
    outcome: str = "SNAPSHOT_COMPLETE",
    conditions: Any = None,
    observations: Any = None,
    diagnostic_reports: Any = None,
    medication_requests: Any = None,
    omit: tuple[str, ...] = (),
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "contractVersion": "v1",
        "destination": "oracle-health-sandbox",
        "contextSource": "CONFIGURED",
        "generatedAt": "2026-09-13T00:00:00Z",
        "outcome": outcome,
        "patient": {"status": "SUCCESS", "resourceType": "Patient"},
        "conditions": collection(retained_count=1) if conditions is None else conditions,
        "observations": collection(retained_count=0) if observations is None else observations,
        "diagnosticReports": collection(retained_count=0) if diagnostic_reports is None else diagnostic_reports,
        "medicationRequests": medication_requests if medication_requests is not None or "medicationRequests" in omit else None,
    }
    for key in omit:
        payload.pop(key, None)
    return payload


def empty_contract(*, outcome: str = "SNAPSHOT_COMPLETE") -> dict[str, Any]:
    return contract(
        outcome=outcome,
        conditions=collection(retained_count=0),
        observations=collection(retained_count=0),
        diagnostic_reports=collection(retained_count=0),
        medication_requests=None,
    )


@pytest.fixture
def settings() -> Settings:
    return Settings(
        model_boundary_base_url="http://model-boundary.test",
        model_boundary_path="/api/model-boundary/v1",
        model_boundary_timeout_seconds=5,
        host="127.0.0.1",
        port=8090,
    )


@pytest.fixture
def valid_contract() -> dict[str, Any]:
    return copy.deepcopy(contract())
