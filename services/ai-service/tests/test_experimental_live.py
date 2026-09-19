"""Opt-in live Gemini test. Default pytest skips this module's live case."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.experimental_fixture import CANONICAL_FIXTURE
from app.main import app, get_settings


def _live_enabled() -> bool:
    return os.getenv("RUN_LIVE_GEMINI_TESTS", "false").strip().lower() == "true"


@pytest.mark.skipif(not _live_enabled(), reason="live Gemini tests are opt-in")
def test_live_gemini_canonical_fixture():
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        pytest.skip("GEMINI_API_KEY is required for live Gemini tests")
    settings = Settings(
        model_boundary_base_url="http://model-boundary.test",
        model_boundary_path="/api/model-boundary/v1",
        model_boundary_timeout_seconds=5,
        model_boundary_service_token="test-model-boundary-token",
        host="127.0.0.1",
        port=8090,
        llm_experimental_enabled=True,
        gemini_api_key=api_key,
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash",
    )
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        response = TestClient(app).post(
            "/internal/experimental-summary",
            json=CANONICAL_FIXTURE,
            headers={"X-Service-Token": "test-model-boundary-token"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "COMPLETED"
        assert body["modelCalled"] is True
        assert body["requiresHumanReview"] is True
        assert body["provider"] == "GEMINI"
        assert body["summary"]
        assert len(body["summary"]) <= 2000
    finally:
        app.dependency_overrides.clear()
