"""HTTP adapter for the Follow-up Agent. Auth, then runtime. No tool or policy logic."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Callable, Optional

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import ValidationError

from app.config import Settings
from app.followup_models import (
    FollowUpRequest,
    FollowUpRequired,
    FollowUpStatus,
    dump_followup_response,
    followup_response,
)
from app.followup_runtime import run_followup_agent
from app.llm_provider import LLMProvider
from app.service_auth import authenticate

log = logging.getLogger("ai-service")

DISABLED_DETAIL = "Follow-up agent is disabled"


def run_followup_http(
    request: Request,
    settings: Settings,
    resolve_provider: Callable[[], Optional[LLMProvider]],
    raw_body: bytes,
) -> Response:
    correlation_id = request.headers.get("X-Correlation-ID") or "missing"
    if not authenticate(request, settings):
        _log(correlation_id, "UNAUTHORIZED", False)
        return Response(status_code=401)

    if not settings.followup_agent_enabled:
        _log(correlation_id, "DISABLED", False)
        return JSONResponse(status_code=503, content={"detail": DISABLED_DETAIL})

    try:
        parsed = FollowUpRequest.model_validate(_load_body(raw_body))
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc

    provider = resolve_provider()
    if provider is None:
        payload = followup_response(
            status=FollowUpStatus.PROVIDER_ERROR,
            run_id=str(uuid.uuid4()),
            case_id=parsed.case_id,
            follow_up_required=FollowUpRequired.UNKNOWN,
            model_called=False,
            reason="provider unavailable",
        )
        _log(correlation_id, payload.status.value, False)
        return JSONResponse(status_code=200, content=dump_followup_response(payload))

    result = run_followup_agent(parsed.case_id, provider)
    _log(correlation_id, result.status.value, result.model_called)
    return JSONResponse(status_code=200, content=dump_followup_response(result))


def _load_body(raw: bytes) -> Any:
    if raw is None or raw.strip() == b"":
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def _log(correlation_id: str, status: str, model_called: bool) -> None:
    line = (
        f"follow_up correlationId={correlation_id} method=POST "
        f"path=/internal/agent/follow-up status={status} "
        f"modelCalled={str(model_called).lower()}"
    )
    lowered = line.lower()
    if "x-service-token=" in lowered or "gemini_api_key=" in lowered:
        raise RuntimeError("follow-up log line must not contain secrets")
    log.info(line)
