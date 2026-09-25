"""Environment settings. Do not log MODEL_BOUNDARY_SERVICE_TOKEN or GEMINI_API_KEY."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    model_boundary_base_url: str
    model_boundary_path: str
    model_boundary_timeout_seconds: float
    model_boundary_service_token: str
    host: str
    port: int
    llm_experimental_enabled: bool = False
    gemini_api_key: str = field(default="", repr=False)
    gemini_model: str = "gemini-flash-latest"
    followup_agent_enabled: bool = False

    @property
    def model_boundary_url(self) -> str:
        base = self.model_boundary_base_url.rstrip("/")
        path = self.model_boundary_path if self.model_boundary_path.startswith("/") else "/" + self.model_boundary_path
        return base + path

    @classmethod
    def from_env(cls) -> Settings:
        timeout_raw = os.getenv("MODEL_BOUNDARY_TIMEOUT_SECONDS", "90").strip()
        port_raw = os.getenv("AI_SERVICE_PORT", "8090").strip()
        try:
            timeout = float(timeout_raw)
        except ValueError as exc:
            raise ValueError("MODEL_BOUNDARY_TIMEOUT_SECONDS must be a number") from exc
        try:
            port = int(port_raw)
        except ValueError as exc:
            raise ValueError("AI_SERVICE_PORT must be an integer") from exc
        if timeout <= 0:
            raise ValueError("MODEL_BOUNDARY_TIMEOUT_SECONDS must be greater than zero")
        enabled_raw = os.getenv("LLM_EXPERIMENTAL_ENABLED", "false").strip().lower()
        followup_raw = os.getenv("FOLLOWUP_AGENT_ENABLED", "false").strip().lower()
        return cls(
            model_boundary_base_url=os.getenv("MODEL_BOUNDARY_BASE_URL", "http://localhost:8081").strip(),
            model_boundary_path=os.getenv("MODEL_BOUNDARY_PATH", "/api/model-boundary/v1").strip(),
            model_boundary_timeout_seconds=timeout,
            model_boundary_service_token=os.getenv("MODEL_BOUNDARY_SERVICE_TOKEN", "").strip(),
            host=os.getenv("AI_SERVICE_HOST", "0.0.0.0").strip() or "0.0.0.0",
            port=port,
            llm_experimental_enabled=enabled_raw == "true",
            gemini_api_key=os.getenv("GEMINI_API_KEY", "").strip(),
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-flash-latest").strip() or "gemini-flash-latest",
            followup_agent_enabled=followup_raw == "true",
        )
