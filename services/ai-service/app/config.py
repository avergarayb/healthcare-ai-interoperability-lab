"""Environment settings. Do not log service tokens, the review form signing secret, the development auth secret, or GEMINI_API_KEY."""

from __future__ import annotations

import math
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
    ai_review_db_path: str = "./data/follow-up-review.sqlite3"
    human_review_form_signing_secret: str = field(default="", repr=False)
    institutional_knowledge_db_path: str = "./data/institutional-knowledge.sqlite3"
    institutional_knowledge_embedding_model: str = "gemini-embedding-001"
    institutional_knowledge_min_score: float = 0.68
    human_session_db_path: str = "./data/human-session.sqlite3"
    human_review_development_auth_enabled: bool = False
    human_review_development_auth_secret: str = field(default="", repr=False)
    human_review_development_principal_id: str = ""
    human_review_development_principal_display_name: str = ""

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
        review_db_path = os.getenv(
            "AI_REVIEW_DB_PATH", "./data/follow-up-review.sqlite3"
        ).strip()
        if not review_db_path:
            raise ValueError("AI_REVIEW_DB_PATH must not be blank")
        knowledge_db_path = os.getenv(
            "INSTITUTIONAL_KNOWLEDGE_DB_PATH",
            "./data/institutional-knowledge.sqlite3",
        ).strip()
        if not knowledge_db_path:
            raise ValueError("INSTITUTIONAL_KNOWLEDGE_DB_PATH must not be blank")
        embedding_model = os.getenv(
            "INSTITUTIONAL_KNOWLEDGE_EMBEDDING_MODEL",
            "gemini-embedding-001",
        ).strip()
        if (
            not embedding_model
            or len(embedding_model) > 128
            or any(character.isspace() for character in embedding_model)
        ):
            raise ValueError("INSTITUTIONAL_KNOWLEDGE_EMBEDDING_MODEL is invalid")
        score_raw = os.getenv("INSTITUTIONAL_KNOWLEDGE_MIN_SCORE", "0.68").strip()
        try:
            min_score = float(score_raw)
        except ValueError as exc:
            raise ValueError("INSTITUTIONAL_KNOWLEDGE_MIN_SCORE must be a number") from exc
        if not math.isfinite(min_score) or not 0 <= min_score <= 1:
            raise ValueError("INSTITUTIONAL_KNOWLEDGE_MIN_SCORE must be between 0 and 1")
        session_db_path = os.getenv(
            "HUMAN_SESSION_DB_PATH", "./data/human-session.sqlite3"
        ).strip()
        if not session_db_path or session_db_path == ":memory:":
            raise ValueError("HUMAN_SESSION_DB_PATH must be a file-backed path")
        development_auth_enabled = (
            os.getenv("HUMAN_REVIEW_DEVELOPMENT_AUTH_ENABLED", "false").strip() == "true"
        )
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
            ai_review_db_path=review_db_path,
            human_review_form_signing_secret=os.getenv("HUMAN_REVIEW_FORM_SIGNING_SECRET", "").strip(),
            institutional_knowledge_db_path=knowledge_db_path,
            institutional_knowledge_embedding_model=embedding_model,
            institutional_knowledge_min_score=min_score,
            human_session_db_path=session_db_path,
            human_review_development_auth_enabled=development_auth_enabled,
            human_review_development_auth_secret=os.getenv(
                "HUMAN_REVIEW_DEVELOPMENT_AUTH_SECRET", ""
            ).strip(),
            human_review_development_principal_id=os.getenv(
                "HUMAN_REVIEW_DEVELOPMENT_PRINCIPAL_ID", ""
            ).strip(),
            human_review_development_principal_display_name=os.getenv(
                "HUMAN_REVIEW_DEVELOPMENT_PRINCIPAL_DISPLAY_NAME", ""
            ).strip(),
        )
