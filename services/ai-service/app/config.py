"""Environment settings. No secrets are required for Task 074."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    model_boundary_base_url: str
    model_boundary_path: str
    model_boundary_timeout_seconds: float
    host: str
    port: int

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
        return cls(
            model_boundary_base_url=os.getenv("MODEL_BOUNDARY_BASE_URL", "http://localhost:8081").strip(),
            model_boundary_path=os.getenv("MODEL_BOUNDARY_PATH", "/api/model-boundary/v1").strip(),
            model_boundary_timeout_seconds=timeout,
            host=os.getenv("AI_SERVICE_HOST", "0.0.0.0").strip() or "0.0.0.0",
            port=port,
        )
