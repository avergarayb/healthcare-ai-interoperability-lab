"""FastAPI entrypoint for the Task 074 consumer and Task 076 experimental summary."""

from __future__ import annotations

import logging
import uuid
from functools import lru_cache

from fastapi import Depends, FastAPI, Request
from fastapi.responses import Response

from app.config import Settings
from app.consumer import consume
from app.experimental_service import load_json_body, run_experimental_summary
from app.gemini_provider import GeminiProvider
from app.llm_provider import LLMProvider
from app.models import AgentContextResult
from app.service_auth import authenticate

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

log = logging.getLogger("ai-service")

app = FastAPI(title="ai-service", version="0.1.0")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_env()


def get_llm_provider(settings: Settings = Depends(get_settings)) -> LLMProvider | None:
    if not settings.gemini_api_key or not settings.gemini_model:
        return None
    return GeminiProvider(api_key=settings.gemini_api_key, model=settings.gemini_model)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/internal/agent-context", response_model=AgentContextResult)
def agent_context(
    request: Request, settings: Settings = Depends(get_settings)
) -> AgentContextResult | Response:
    if not authenticate(request, settings):
        correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        log.info(
            "agent_context correlationId=%s method=GET path=/internal/agent-context status=UNAUTHORIZED modelCalled=false",
            correlation_id,
        )
        return Response(status_code=401)
    correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
    return consume(settings, correlation_id)


@app.post("/internal/experimental-summary")
async def experimental_summary(
    request: Request,
    settings: Settings = Depends(get_settings),
    provider: LLMProvider = Depends(get_llm_provider),
) -> Response:
    body = load_json_body(await request.body())
    return run_experimental_summary(request, settings, provider, body)
