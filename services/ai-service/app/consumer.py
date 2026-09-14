"""Consume GET /api/model-boundary/v1. Never calls a language model."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Literal, Optional

import httpx

from app.config import Settings
from app.models import AgentContextResult, received, rejected

log = logging.getLogger("ai-service")

VALID_OUTCOMES = frozenset(
    {
        "SNAPSHOT_COMPLETE",
        "SNAPSHOT_PARTIAL",
        "SNAPSHOT_UNAVAILABLE",
        "PATIENT_CONTEXT_NOT_CONFIGURED",
        "AUTHENTICATION_REQUIRED",
    }
)
RECEIVED_OUTCOMES = frozenset({"SNAPSHOT_COMPLETE", "SNAPSHOT_PARTIAL"})
REQUIRED_KEYS = (
    "contractVersion",
    "outcome",
    "patient",
    "conditions",
    "observations",
    "diagnosticReports",
    "medicationRequests",
)
COLLECTION_KEYS = (
    "conditions",
    "observations",
    "diagnosticReports",
    "medicationRequests",
)


@dataclass(frozen=True)
class BoundaryResponse:
    kind: Literal["http", "timeout", "connection"]
    status_code: Optional[int] = None
    body_text: Optional[str] = None


def fetch_contract(settings: Settings, client: Optional[httpx.Client] = None) -> BoundaryResponse:
    close_client = client is None
    http_client = client or httpx.Client(timeout=settings.model_boundary_timeout_seconds)
    try:
        headers = {}
        if settings.model_boundary_service_token:
            headers["X-Service-Token"] = settings.model_boundary_service_token
        response = http_client.get(settings.model_boundary_url, headers=headers)
        return BoundaryResponse(kind="http", status_code=response.status_code, body_text=response.text)
    except httpx.TimeoutException:
        return BoundaryResponse(kind="timeout")
    except httpx.RequestError:
        return BoundaryResponse(kind="connection")
    finally:
        if close_client:
            http_client.close()


def evaluate(response: BoundaryResponse) -> AgentContextResult:
    if response.kind == "timeout":
        return rejected(reason="boundary_timeout")
    if response.kind == "connection":
        return rejected(reason="boundary_connection_error")

    status_code = response.status_code
    if status_code is None:
        return rejected(reason="invalid_contract")
    if 400 <= status_code <= 499:
        return rejected(reason="boundary_http_4xx")
    if 500 <= status_code <= 599:
        return rejected(reason="boundary_http_5xx")
    if status_code != 200:
        return rejected(reason="invalid_contract")

    payload, error = parse_contract(response.body_text)
    if error is not None:
        return error
    assert payload is not None

    version = str(payload["contractVersion"]).strip()
    outcome = payload["outcome"]
    if outcome not in RECEIVED_OUTCOMES:
        return rejected(
            reason="boundary_outcome_not_success",
            contract_version=version,
            outcome=outcome,
        )
    if not has_retained_context(payload):
        return rejected(reason="empty_context", contract_version=version, outcome=outcome)
    return received(contract_version=version, outcome=outcome)


def parse_contract(body_text: Optional[str]) -> tuple[Optional[dict[str, Any]], Optional[AgentContextResult]]:
    if body_text is None or body_text.strip() == "":
        return None, rejected(reason="invalid_contract")
    try:
        payload = json.loads(body_text)
    except json.JSONDecodeError:
        return None, rejected(reason="invalid_contract")
    if not isinstance(payload, dict):
        return None, rejected(reason="invalid_contract")
    for key in REQUIRED_KEYS:
        if key not in payload:
            return None, rejected(reason="invalid_contract")
    version = payload.get("contractVersion")
    if not isinstance(version, str) or version.strip() == "":
        return None, rejected(reason="invalid_contract")
    outcome = payload.get("outcome")
    if outcome not in VALID_OUTCOMES:
        return None, rejected(reason="invalid_contract")
    if not collections_are_evaluable(payload):
        return None, rejected(reason="invalid_contract")
    return payload, None


def collections_are_evaluable(payload: dict[str, Any]) -> bool:
    for key in COLLECTION_KEYS:
        collection = payload[key]
        if collection is None:
            continue
        if not isinstance(collection, dict):
            return False
        if "retainedCount" not in collection:
            continue
        retained = collection["retainedCount"]
        if retained is None:
            continue
        if isinstance(retained, bool) or not isinstance(retained, int):
            return False
    return True


def has_retained_context(payload: dict[str, Any]) -> bool:
    for key in COLLECTION_KEYS:
        collection = payload[key]
        if collection is None:
            continue
        retained = collection.get("retainedCount")
        if isinstance(retained, int) and not isinstance(retained, bool) and retained > 0:
            return True
    return False


def consume(settings: Settings, correlation_id: str, client: Optional[httpx.Client] = None) -> AgentContextResult:
    started = _monotonic_ms()
    response = fetch_contract(settings, client)
    result = evaluate(response)
    duration_ms = _monotonic_ms() - started
    log.info(
        "agent_context correlationId=%s method=GET path=%s javaHttpStatus=%s durationMs=%s status=%s reason=%s modelCalled=false",
        correlation_id,
        settings.model_boundary_path,
        response.status_code if response.status_code is not None else "",
        duration_ms,
        result.status,
        result.reason or "",
    )
    return result


def _monotonic_ms() -> int:
    import time

    return int(time.monotonic() * 1000)
