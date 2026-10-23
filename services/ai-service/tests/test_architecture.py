from __future__ import annotations

import ast
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
    "langgraph_workflow_orchestration.py",
}
# These modules reuse the FHIR read implementation. They must not import LangGraph or Gemini.
FHIR_REUSE_MODULES = {
    "clinical_read_client.py",
    "clinical_review_context.py",
    "clinical_review_context_http.py",
    "federated_protocol_evaluation.py",
    "missed_follow_up_service.py",
    "longitudinal_context.py",
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
        if path.name in LESSON_MODULES or path.name in FHIR_REUSE_MODULES or path.name == "followup_service.py":
            continue
        assert "langgraph" not in _read(path)
    for name in FHIR_REUSE_MODULES:
        source = _read(APP / name)
        assert "import langgraph" not in source
        assert "from langgraph" not in source
        assert "gemini" not in source
        assert "langgraph_gemini" not in source
        assert "langgraph_followup_workflow" not in source
        assert "followupworkflow" not in source
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


# Operational Python reaches Java through Clinical Read. The legacy direct
# reader stays in langgraph_fhir_hapi.py for laboratory tools and tests.
_LEGACY_HAPI_MODULE = "langgraph_fhir_hapi"
_LEGACY_HAPI_NAMES = frozenset({"HapiReadClient", "FHIR_BASE_URL"})
_LEGACY_HAPI_FILE = "langgraph_fhir_hapi.py"
_OPERATIONAL_FACTORIES = (
    ("langgraph_followup_workflow.py", "build_live_followup_workflow"),
    ("missed_follow_up_service.py", "_live_adapter"),
    ("clinical_review_context_http.py", "_fhir_client"),
    ("langgraph_workflow_orchestration.py", "build_live_ports"),
)


def _constant_string(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _dotted_names_legacy_module(dotted: str | None) -> bool:
    return bool(dotted) and _LEGACY_HAPI_MODULE in dotted.split(".")


def _is_environ(node: ast.AST) -> bool:
    if isinstance(node, ast.Name) and node.id == "environ":
        return True
    return isinstance(node, ast.Attribute) and node.attr == "environ"


def _call_strings(node: ast.Call) -> tuple[str, ...]:
    values = [_constant_string(arg) for arg in node.args]
    values.extend(_constant_string(keyword.value) for keyword in node.keywords)
    return tuple(value for value in values if value is not None)


def _call_name(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _legacy_hapi_uses(tree: ast.AST) -> tuple[str, ...]:
    """Name operational imports, references, and FHIR_BASE_URL reads.

    Comments, docstrings, and other plain strings are not uses.
    """
    found: list[str] = []

    def add(node: ast.AST, reason: str) -> None:
        found.append(f"line {getattr(node, 'lineno', 0)}: {reason}")

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if (
                    _dotted_names_legacy_module(alias.name)
                    or alias.name in _LEGACY_HAPI_NAMES
                    or alias.asname in _LEGACY_HAPI_NAMES
                ):
                    add(node, f"import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if _dotted_names_legacy_module(node.module):
                add(node, f"from {node.module}")
            else:
                for alias in node.names:
                    if alias.name in _LEGACY_HAPI_NAMES or alias.asname in _LEGACY_HAPI_NAMES:
                        add(node, f"imported name {alias.name}")
        elif isinstance(node, ast.Name) and node.id in _LEGACY_HAPI_NAMES:
            add(node, f"name {node.id}")
        elif isinstance(node, ast.Attribute) and node.attr in _LEGACY_HAPI_NAMES | {_LEGACY_HAPI_MODULE}:
            add(node, f"attribute {node.attr}")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name in _LEGACY_HAPI_NAMES:
            add(node, f"definition {node.name}")
        elif isinstance(node, ast.Call):
            called = _call_name(node)
            arguments = _call_strings(node)
            if called in {"import_module", "__import__"} and any(
                _dotted_names_legacy_module(argument) for argument in arguments
            ):
                add(node, f"dynamic import {called}")
            elif called == "getenv" and "FHIR_BASE_URL" in arguments:
                add(node, "getenv FHIR_BASE_URL")
            elif (
                called == "get"
                and isinstance(node.func, ast.Attribute)
                and _is_environ(node.func.value)
                and "FHIR_BASE_URL" in arguments
            ):
                add(node, "environ.get FHIR_BASE_URL")
        elif isinstance(node, ast.Subscript) and _constant_string(node.slice) == "FHIR_BASE_URL":
            add(node, "subscript FHIR_BASE_URL")
        elif isinstance(node, ast.Compare) and _constant_string(node.left) == "FHIR_BASE_URL":
            if any(isinstance(operator, ast.In) for operator in node.ops) and any(
                _is_environ(comparator) for comparator in node.comparators
            ):
                add(node, "membership FHIR_BASE_URL")
    return tuple(found)


def _module_function(tree: ast.AST, name: str) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    for node in tree.body if isinstance(tree, ast.Module) else []:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    return None


def _calls_clinical_read_from_settings(function: ast.AST) -> bool:
    for node in ast.walk(function):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "from_settings":
            continue
        value = node.func.value
        if isinstance(value, ast.Name) and value.id == "ClinicalReadClient":
            return True
    return False


def test_operational_python_reaches_java_through_clinical_read():
    """Operational app modules do not name the legacy direct HAPI reader.

    The service path is Python to Clinical Read API to Java. Laboratory
    scripts and tests may still import langgraph_fhir_hapi.py.
    """
    offenders: list[str] = []
    for path in sorted(APP.glob("*.py")):
        if path.name == _LEGACY_HAPI_FILE:
            continue
        uses = _legacy_hapi_uses(ast.parse(path.read_text(encoding="utf-8")))
        offenders.extend(f"{path.name} {use}" for use in uses)
    assert offenders == []


def test_operational_factories_construct_clinical_read_from_settings():
    for filename, function_name in _OPERATIONAL_FACTORIES:
        tree = ast.parse((APP / filename).read_text(encoding="utf-8"))
        function = _module_function(tree, function_name)
        assert function is not None
        assert _calls_clinical_read_from_settings(function)
        assert _legacy_hapi_uses(function) == ()


def test_legacy_hapi_scan_rejects_synthetic_operational_uses():
    samples = (
        "from app.langgraph_fhir_hapi import HapiReadClient\n",
        "import app.langgraph_fhir_hapi\n",
        "def build():\n    return HapiReadClient()\n",
        "import os\nvalue = os.environ['FHIR_BASE_URL']\n",
        "import os\nif 'FHIR_BASE_URL' in os.environ:\n    value = os.getenv('FHIR_BASE_URL')\n",
        "import importlib\nimportlib.import_module('app.langgraph_fhir_hapi')\n",
        "def build_live_followup_workflow():\n    return HapiReadClient()\n",
    )
    for sample in samples:
        tree = ast.parse(sample)
        assert _legacy_hapi_uses(tree), sample
    factory = _module_function(ast.parse(samples[-1]), "build_live_followup_workflow")
    assert factory is not None
    assert _calls_clinical_read_from_settings(factory) is False


def test_legacy_hapi_scan_ignores_comments_docstrings_and_plain_strings():
    source = '''
"""HapiReadClient reads FHIR_BASE_URL."""
# from app.langgraph_fhir_hapi import HapiReadClient
def explain():
    """Operational code does not construct HapiReadClient."""
    return "FHIR_BASE_URL is a laboratory variable"
'''
    assert _legacy_hapi_uses(ast.parse(source)) == ()
