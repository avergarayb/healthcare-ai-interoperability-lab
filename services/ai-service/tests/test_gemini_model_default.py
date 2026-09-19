from __future__ import annotations

from app.config import Settings
from app.experimental_models import DEFAULT_MODEL


def test_dataclass_default_is_flash_latest():
    settings = Settings(
        model_boundary_base_url="http://model-boundary.test",
        model_boundary_path="/api/model-boundary/v1",
        model_boundary_timeout_seconds=5,
        model_boundary_service_token="",
        host="127.0.0.1",
        port=8090,
    )
    assert settings.gemini_model == "gemini-flash-latest"
    assert DEFAULT_MODEL == "gemini-flash-latest"


def test_from_env_without_gemini_model_uses_flash_latest(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    settings = Settings.from_env()
    assert settings.gemini_model == "gemini-flash-latest"


def test_from_env_blank_gemini_model_uses_flash_latest(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "   ")
    settings = Settings.from_env()
    assert settings.gemini_model == "gemini-flash-latest"


def test_from_env_override_is_respected(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-flash")
    settings = Settings.from_env()
    assert settings.gemini_model == "gemini-2.5-flash"
