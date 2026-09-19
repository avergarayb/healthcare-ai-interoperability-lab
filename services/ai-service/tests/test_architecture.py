from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
REQUIREMENTS = (ROOT / "requirements.txt").read_text(encoding="utf-8").lower()
APP_SOURCE = "\n".join(path.read_text(encoding="utf-8") for path in APP.glob("*.py")).lower()

ALLOWED_MODEL_DEPENDENCY = "google-genai"

FORBIDDEN_DEPENDENCIES = (
    "openai",
    "anthropic",
    "langchain",
    "langgraph",
    "ollama",
    "boto3",
    "google-generativeai",
    "fhirclient",
    "fhir.resources",
)

FORBIDDEN_SOURCE = (
    "openai",
    "anthropic",
    "langchain",
    "langgraph",
    "ollama",
    "fhirclient",
    "open.epic.com",
    "fhir.cerner.com",
    "authorization: bearer",
)


def test_requirements_have_no_language_model_or_clinical_clients():
    for name in FORBIDDEN_DEPENDENCIES:
        assert name not in REQUIREMENTS
    assert ALLOWED_MODEL_DEPENDENCY in REQUIREMENTS
    assert "google-genai==" in REQUIREMENTS


def test_app_source_does_not_call_a_language_model_or_clinical_host():
    for token in FORBIDDEN_SOURCE:
        assert token not in APP_SOURCE


def test_app_source_does_not_import_vendor_or_smart_clients():
    assert "from fhir" not in APP_SOURCE
    assert "import fhir" not in APP_SOURCE
    assert "smartonfhir" not in APP_SOURCE
    assert "hl7.fhir" not in APP_SOURCE
