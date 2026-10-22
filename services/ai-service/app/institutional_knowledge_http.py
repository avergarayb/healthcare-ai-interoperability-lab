"""Authenticated internal retrieval for institutional knowledge."""

from __future__ import annotations

import json
import logging
import time

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import ValidationError

from app.config import Settings
from app.institutional_knowledge import (
    KnowledgeRetrieveRequest,
    RetrievalResult,
    UnavailableInstitutionalKnowledge,
)
from app.service_auth import authenticate

log = logging.getLogger("ai-service")


def retrieve_institutional_knowledge_http(request: Request, settings: Settings, raw_body: bytes) -> Response:
    started = time.perf_counter()
    correlation_id = request.headers.get("X-Correlation-ID") or "missing"
    if not authenticate(request, settings):
        _log(correlation_id, "UNAUTHORIZED", "-", "-", 0, 0, "-", started)
        return Response(status_code=401)
    try:
        parsed = KnowledgeRetrieveRequest.model_validate(_load_body(raw_body))
    except ValidationError as exc:
        _log(correlation_id, "INVALID", "-", "-", 0, 0, "-", started)
        raise RequestValidationError(exc.errors()) from exc
    index = getattr(request.app.state, "institutional_knowledge", None)
    if index is None:
        index = UnavailableInstitutionalKnowledge()
    try:
        result = index.retrieve(parsed)
    except Exception:
        result = RetrievalResult(status="UNAVAILABLE", protocol_id=parsed.protocolId, reason="index_not_ready")
    status_code = 200 if result.status != "UNAVAILABLE" else 503
    chunk_ids = ",".join(chunk.chunk_id for chunk in result.chunks) or "-"
    document_ids = ",".join(dict.fromkeys(chunk.document_id for chunk in result.chunks)) or "-"
    _log(
        correlation_id,
        result.status,
        parsed.protocolId,
        result.reason or "-",
        len(result.chunks),
        len(parsed.reasonCodes or ()),
        chunk_ids,
        started,
        document_ids=document_ids,
    )
    return JSONResponse(status_code=status_code, content=result.as_dict())


def _load_body(raw: bytes):
    if raw is None or raw.strip() == b"":
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def _log(
    correlation_id: str,
    status: str,
    protocol_id: str,
    reason: str,
    result_count: int,
    reason_code_count: int,
    chunk_ids: str,
    started: float,
    document_ids: str = "-",
) -> None:
    duration_ms = int((time.perf_counter() - started) * 1000)
    line = (
        "knowledge_retrieve correlationId=%s method=POST path=/internal/knowledge/retrieve "
        "status=%s protocolId=%s reason=%s resultCount=%s reasonCodeCount=%s "
        "documentIds=%s chunkIds=%s durationMs=%s"
        % (
            correlation_id,
            status,
            protocol_id,
            reason,
            result_count,
            reason_code_count,
            document_ids,
            chunk_ids,
            duration_ms,
        )
    )
    lowered = line.lower()
    if "x-service-token=" in lowered or "gemini_api_key=" in lowered:
        raise RuntimeError("knowledge log line must not contain secrets")
    log.info(line)
