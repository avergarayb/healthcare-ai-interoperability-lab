"""HTTP adapter for follow-up. Auth, flag, validation, then FollowUpWorkflow.run."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Callable

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import ValidationError

from app.config import Settings
from app.followup_models import (
    Evidence,
    FollowUpEndpointResponse,
    FollowUpEndpointStatus,
    FollowUpRequest,
    FollowUpRequired,
    dump_followup_endpoint_response,
)
from app.langgraph_fhir_client import InMemoryAuditSink, default_clock
from app.langgraph_followup_workflow import (
    FollowUpWorkflow,
    FollowUpWorkflowResult,
    build_live_followup_workflow,
)
from app.service_auth import authenticate

log = logging.getLogger("ai-service")

DISABLED_DETAIL = "Follow-up agent is disabled"
WORKFLOW_FAILED_DETAIL = "Follow-up workflow failed"

_HTTP_STATUS = {
    "finish": FollowUpEndpointStatus.COMPLETED,
    "denied": FollowUpEndpointStatus.DENIED,
    "unavailable": FollowUpEndpointStatus.UNAVAILABLE,
    "limit": FollowUpEndpointStatus.LIMIT,
}


def build_followup_workflow(run_id: str) -> FollowUpWorkflow:
    """Compose the live workflow. The caller owns run_id."""
    return build_live_followup_workflow(
        InMemoryAuditSink(),
        clock=default_clock,
        run_id=run_id,
    )


def run_followup_http(
    request: Request,
    settings: Settings,
    raw_body: bytes,
    *,
    build_workflow: Callable[[str], FollowUpWorkflow] | None = None,
) -> Response:
    correlation_id = request.headers.get("X-Correlation-ID") or "missing"
    if not authenticate(request, settings):
        _log(correlation_id, "UNAUTHORIZED")
        return Response(status_code=401)

    if not settings.followup_agent_enabled:
        _log(correlation_id, "DISABLED")
        return JSONResponse(status_code=503, content={"detail": DISABLED_DETAIL})

    try:
        parsed = FollowUpRequest.model_validate(_load_body(raw_body))
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc

    run_id = str(uuid.uuid4())
    factory = build_workflow or build_followup_workflow
    workflow = factory(run_id)
    try:
        result = workflow.run(parsed.case_id)
    except Exception:
        _log(correlation_id, "error")
        return JSONResponse(status_code=502, content={"detail": WORKFLOW_FAILED_DETAIL})

    payload = _project(result)
    if payload is None:
        _log(correlation_id, "error")
        return JSONResponse(status_code=502, content={"detail": WORKFLOW_FAILED_DETAIL})
    _log(correlation_id, payload.status.value)
    return JSONResponse(status_code=200, content=dump_followup_endpoint_response(payload))


def _project(result: FollowUpWorkflowResult) -> FollowUpEndpointResponse | None:
    status = _HTTP_STATUS.get(result.status)
    allowed = {item.value for item in FollowUpRequired}
    if status is None or result.run_id == "" or result.follow_up_required not in allowed:
        return None
    return FollowUpEndpointResponse(
        runId=result.run_id,
        caseId=result.case_id,
        status=status,
        followUpRequired=FollowUpRequired(result.follow_up_required),
        answer=result.final_answer,
        evidence=_evidence(result.evidence),
    )


def _evidence(evidence: list[dict[str, Any]]) -> list[Evidence]:
    items: list[Evidence] = []
    for entry in evidence:
        tool = entry.get("tool")
        resources = entry.get("resources")
        if not isinstance(tool, str) or not isinstance(resources, list):
            continue
        for reference in resources:
            if isinstance(reference, str) and reference:
                items.append(Evidence(tool=tool, id=reference))
    return items


def _load_body(raw: bytes) -> Any:
    if raw is None or raw.strip() == b"":
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def _log(correlation_id: str, status: str) -> None:
    line = (
        f"follow_up correlationId={correlation_id} method=POST "
        f"path=/internal/agent/follow-up status={status}"
    )
    lowered = line.lower()
    if "x-service-token=" in lowered or "gemini_api_key=" in lowered:
        raise RuntimeError("follow-up log line must not contain secrets")
    log.info(line)
