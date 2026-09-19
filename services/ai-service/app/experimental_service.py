"""Fail-closed experimental summary. Does not call FHIR, SMART, or Java."""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Optional

from fastapi import Request
from fastapi.responses import JSONResponse, Response

from app.config import Settings
from app.experimental_fixture import is_canonical_fixture
from app.experimental_models import (
    DEFAULT_MODEL,
    MAX_SUMMARY_CHARS,
    ExperimentalSummaryRequest,
    dump_response,
    experimental_response,
)
from app.llm_provider import LLMProvider, ProviderGeneration

log = logging.getLogger("ai-service")

USE_CASE = "experimental-summary"


def authenticate(request: Request, settings: Settings) -> bool:
    presented = request.headers.get("X-Service-Token")
    configured = settings.model_boundary_service_token
    if not configured:
        return False
    if presented is None or presented == "":
        return False
    return presented == configured


def gemini_configured(settings: Settings) -> bool:
    return bool(settings.gemini_api_key) and bool(settings.gemini_model)


def parse_experimental_request(body: Any) -> Optional[ExperimentalSummaryRequest]:
    if not isinstance(body, dict):
        return None
    try:
        return ExperimentalSummaryRequest.model_validate(body)
    except Exception:
        return None


def _provider_tried_to_set_governance(text: str) -> bool:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return False
    if not isinstance(parsed, dict):
        return False
    return "requiresHumanReview" in parsed or "modelCalled" in parsed


def apply_provider_generation(
    generation: ProviderGeneration,
    settings: Settings,
) -> tuple[int, dict]:
    model = settings.gemini_model or DEFAULT_MODEL
    if generation.error == "timeout":
        return 504, dump_response(
            experimental_response(status="PROVIDER_ERROR", model_called=True, model=model)
        )
    if generation.error in {"http_4xx", "http_5xx", "malformed", "empty"}:
        return 502, dump_response(
            experimental_response(status="PROVIDER_ERROR", model_called=True, model=model)
        )
    text = generation.text
    if text is None or text.strip() == "":
        return 502, dump_response(
            experimental_response(status="PROVIDER_ERROR", model_called=True, model=model)
        )
    if len(text) > MAX_SUMMARY_CHARS or _provider_tried_to_set_governance(text):
        return 502, dump_response(
            experimental_response(status="PROVIDER_ERROR", model_called=True, model=model)
        )
    return 200, dump_response(
        experimental_response(
            status="COMPLETED",
            model_called=True,
            summary=text,
            model=model,
        )
    )


def emit_audit(
    *,
    correlation_id: str,
    status: str,
    model_called: bool,
    duration_ms: int,
    model: str,
) -> None:
    line = (
        f"experimental_llm_call correlationId={correlation_id} useCase={USE_CASE} "
        f"provider=GEMINI model={model} promptVersion=experimental-summary-v1 "
        f"durationMs={duration_ms} status={status} modelCalled={str(model_called).lower()}"
    )
    lowered = line.lower()
    if (
        "access_token=" in lowered
        or "gemini_api_key=" in lowered
        or "x-service-token=" in lowered
    ):
        raise RuntimeError("experimental audit line must not contain secrets")
    log.info(line)


def run_experimental_summary(
    request: Request,
    settings: Settings,
    provider: LLMProvider | None,
    body: Any,
) -> Response:
    started = time.monotonic()
    correlation_id = request.headers.get("X-Correlation-ID") or "missing"
    model = settings.gemini_model or DEFAULT_MODEL

    def finish(status_code: int, payload: Optional[dict], model_called: bool, status: str) -> Response:
        duration_ms = int((time.monotonic() - started) * 1000)
        emit_audit(
            correlation_id=correlation_id,
            status=status,
            model_called=model_called,
            duration_ms=duration_ms,
            model=model,
        )
        if payload is None:
            return Response(status_code=status_code)
        return JSONResponse(status_code=status_code, content=payload)

    if not authenticate(request, settings):
        duration_ms = int((time.monotonic() - started) * 1000)
        emit_audit(
            correlation_id=correlation_id,
            status="UNAUTHORIZED",
            model_called=False,
            duration_ms=duration_ms,
            model=model,
        )
        return Response(status_code=401)

    if not settings.llm_experimental_enabled:
        payload = dump_response(
            experimental_response(status="DISABLED", model_called=False, model=model)
        )
        return finish(503, payload, False, "DISABLED")

    parsed = parse_experimental_request(body)
    if parsed is None or not is_canonical_fixture(parsed):
        payload = dump_response(
            experimental_response(status="VALIDATION_ERROR", model_called=False, model=model)
        )
        return finish(422, payload, False, "VALIDATION_ERROR")

    if not gemini_configured(settings) or provider is None:
        payload = dump_response(
            experimental_response(status="PROVIDER_ERROR", model_called=False, model=model)
        )
        return finish(503, payload, False, "PROVIDER_ERROR")

    generation = provider.generate_summary(parsed)
    status_code, payload = apply_provider_generation(generation, settings)
    return finish(status_code, payload, payload["modelCalled"], payload["status"])


def load_json_body(raw: bytes) -> Any:
    if raw is None or raw.strip() == b"":
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
