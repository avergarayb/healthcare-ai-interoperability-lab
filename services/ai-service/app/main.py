"""FastAPI entrypoint for the Task 074 consumer, Task 076 summary, and Follow-up Agent."""

from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from app.config import Settings
from app.consumer import consume
from app.experimental_service import load_json_body, run_experimental_summary
from app.followup_service import run_followup_http
from app.missed_follow_up_service import run_missed_follow_up_http
from app.clinical_review_context_http import get_clinical_review_context_http
from app.human_review_client import close_review_case, render_review_case, render_review_queue
from app.followup_review_http import (
    close_review_case_http,
    get_review_case_http,
    list_review_cases_http,
)
from app.followup_review_sqlite import SQLiteFollowUpReviewCaseRepository
from app.gemini_provider import GeminiProvider
from app.institutional_knowledge import attach_institutional_knowledge
from app.institutional_knowledge_http import retrieve_institutional_knowledge_http
from app.llm_provider import LLMProvider
from app.models import AgentContextResult
from app.service_auth import authenticate

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

log = logging.getLogger("ai-service")

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_env()


@asynccontextmanager
async def lifespan(application: FastAPI):
    settings = get_settings()
    repository = SQLiteFollowUpReviewCaseRepository(settings.ai_review_db_path)
    repository.initialize()
    application.state.followup_review_repository = repository
    attach_institutional_knowledge(application, settings)
    try:
        yield
    finally:
        if hasattr(application.state, "followup_review_repository"):
            del application.state.followup_review_repository
        if hasattr(application.state, "institutional_knowledge"):
            del application.state.institutional_knowledge


app = FastAPI(title="ai-service", version="0.1.0", lifespan=lifespan)
# Public Human Review demo assets only. Do not place other files in this directory.
app.mount(
    "/review-static",
    StaticFiles(directory=Path(__file__).resolve().parent / "static" / "human_review"),
    name="review-static",
)


def get_llm_provider(settings: Settings = Depends(get_settings)) -> LLMProvider | None:
    if not settings.gemini_api_key or not settings.gemini_model:
        return None
    return GeminiProvider(api_key=settings.gemini_api_key, model=settings.gemini_model)


@app.get("/review-cases")
def review_cases(request: Request, settings: Settings = Depends(get_settings)) -> Response:
    return render_review_queue(request, settings)


@app.get("/review-cases/{review_case_id}")
def review_case(review_case_id: str, request: Request, settings: Settings = Depends(get_settings)) -> Response:
    return render_review_case(request, settings, review_case_id)


@app.post("/review-cases/{review_case_id}/close")
async def review_case_close(
    review_case_id: str,
    request: Request,
    settings: Settings = Depends(get_settings),
) -> Response:
    return close_review_case(
        request,
        settings,
        review_case_id,
        await request.body(),
        request.headers.get("content-type"),
    )


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


@app.post("/internal/agent/follow-up")
async def follow_up(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> Response:
    return run_followup_http(request, settings, await request.body())


@app.post("/internal/agent/missed-follow-up")
async def missed_follow_up(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> Response:
    return run_missed_follow_up_http(request, settings, await request.body())


@app.get("/internal/follow-up-review-cases")
def list_follow_up_review_cases(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> Response:
    return list_review_cases_http(request, settings)


@app.get("/internal/follow-up-review-cases/{review_case_id}/clinical-context")
def get_follow_up_review_clinical_context(
    review_case_id: str,
    request: Request,
    settings: Settings = Depends(get_settings),
) -> Response:
    return get_clinical_review_context_http(request, settings, review_case_id)


@app.get("/internal/follow-up-review-cases/{review_case_id}")
def get_follow_up_review_case(
    review_case_id: str,
    request: Request,
    settings: Settings = Depends(get_settings),
) -> Response:
    return get_review_case_http(request, settings, review_case_id)


@app.post("/internal/follow-up-review-cases/{review_case_id}/close")
async def close_follow_up_review_case(
    review_case_id: str,
    request: Request,
    settings: Settings = Depends(get_settings),
) -> Response:
    return close_review_case_http(
        request,
        settings,
        review_case_id,
        await request.body(),
    )


@app.post("/internal/knowledge/retrieve")
async def retrieve_institutional_knowledge(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> Response:
    return retrieve_institutional_knowledge_http(request, settings, await request.body())
