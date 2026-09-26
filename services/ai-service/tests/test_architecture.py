from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
REQUIREMENTS = (ROOT / "requirements.txt").read_text(encoding="utf-8").lower()


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8").lower()


# The consolidated follow-up workflow may import LangGraph. The HTTP Follow-up
# Agent stays outside these modules, and the langchain package stays out.
LESSON_MODULES = {
    "langgraph_fhir_client.py",
    "langgraph_fhir_hapi.py",
    "langgraph_fhir_followup.py",
    "langgraph_gemini_fhir_followup.py",
    "langgraph_followup_workflow.py",
}
PRODUCTION_SOURCE = "\n".join(
    _read(path) for path in sorted(APP.glob("*.py")) if path.name not in LESSON_MODULES
)
LESSON_SOURCE = "\n".join(_read(APP / name) for name in sorted(LESSON_MODULES))
APP_SOURCE = f"{PRODUCTION_SOURCE}\n{LESSON_SOURCE}"

ALLOWED_MODEL_DEPENDENCY = "google-genai"

FORBIDDEN_DEPENDENCIES = (
    "openai",
    "anthropic",
    "langchain",
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
    assert "langgraph==1.2.12" in REQUIREMENTS
    assert ALLOWED_MODEL_DEPENDENCY in REQUIREMENTS
    assert "google-genai==" in REQUIREMENTS


def test_app_source_does_not_call_a_language_model_or_clinical_host():
    for token in FORBIDDEN_SOURCE:
        if token in {"langgraph", "langchain"}:
            assert "langchain_core" not in PRODUCTION_SOURCE
            assert "import langgraph" not in PRODUCTION_SOURCE
            assert "from langgraph" not in PRODUCTION_SOURCE
            assert "import langchain" not in PRODUCTION_SOURCE
            assert "from langchain" not in PRODUCTION_SOURCE
            continue
        assert token not in APP_SOURCE
    for path in sorted(APP.glob("*.py")):
        if path.name in LESSON_MODULES or path.name == "followup_service.py":
            continue
        assert "langgraph" not in _read(path)
    lesson_without_core = LESSON_SOURCE.replace("langchain_core", "")
    assert "import langchain" not in lesson_without_core
    assert "from langchain " not in lesson_without_core
    assert "from langchain." not in lesson_without_core
    assert "from langgraph.graph import" in LESSON_SOURCE
    assert "toolnode" in LESSON_SOURCE


def test_followup_endpoint_calls_the_workflow_only():
    service = _read(APP / "followup_service.py")
    main = _read(APP / "main.py")
    assert "from app.langgraph_followup_workflow import" in service
    assert "followupworkflow" in service
    assert "build_followup_workflow" in service
    for name in (
        "followup_runtime",
        "followup_prompt",
        "followup_trace",
        "followup_tools",
        "followup_fixtures",
        "followup_policy",
        "generate_text",
        "httpx",
        "hapireadclient",
    ):
        assert name not in service
    assert "followup_runtime" not in main
    assert "get_llm_provider" not in _read(APP / "main.py").split("def follow_up")[1].split("def ")[0]


def test_app_source_does_not_import_vendor_or_smart_clients():
    assert "from fhir" not in APP_SOURCE
    assert "import fhir" not in APP_SOURCE
    assert "smartonfhir" not in APP_SOURCE
    assert "hl7.fhir" not in APP_SOURCE
