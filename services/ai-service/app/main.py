"""FastAPI entrypoint for the Task 074 model-boundary consumer."""

from __future__ import annotations

import logging
import uuid
from functools import lru_cache

from fastapi import Depends, FastAPI, Request

from app.config import Settings
from app.consumer import consume
from app.models import AgentContextResult

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

app = FastAPI(title="ai-service", version="0.1.0")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_env()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/internal/agent-context", response_model=AgentContextResult)
def agent_context(request: Request, settings: Settings = Depends(get_settings)) -> AgentContextResult:
    correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
    return consume(settings, correlation_id)
