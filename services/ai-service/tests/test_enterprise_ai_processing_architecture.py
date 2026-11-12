"""C01/C02 closed architecture inventories plus inert negative controls."""
import ast
from pathlib import Path

import pytest

from tests.test_enterprise_ai_processing import _assert_c01_pure_ast


ROOT = Path(__file__).resolve().parents[1] / "app"
C01 = frozenset({"__init__.py", "models.py", "policy.py"})
C02 = frozenset({"execution_types.py", "gateway.py", "fake_model.py", "sqlite_ledger.py",
                 "source_boundary.py", "grounding.py", "answer.py", "authorization.py",
                 "delivery_sink.py", "orchestration.py", "composition.py"})
IMPORTS = {
    "answer.py": frozenset({"dataclasses", ".execution_types"}),
    "authorization.py": frozenset({
        ".execution_types", ".grounding", ".models", ".policy", "..enterprise_connectors.models"}),
    "delivery_sink.py": frozenset({".execution_types"}),
    "orchestration.py": frozenset({"asyncio", "typing", "langgraph.errors", "langgraph.graph", "langsmith"}),
    "composition.py": frozenset({
        "asyncio", "sys", "dataclasses", "threading", ".answer", ".authorization", ".delivery_sink",
        ".execution_types", ".grounding", ".orchestration", ".source_boundary", ".sqlite_ledger",
        "..enterprise_connectors.models"}),
    "grounding.py": frozenset({"dataclasses"}),
    "source_boundary.py": frozenset({
        "asyncio", "contextvars", "dataclasses", "datetime", "threading", "uuid",
        ".execution_types", ".gateway", ".grounding", ".models", ".sqlite_ledger",
        "..enterprise_connectors.models", "..enterprise_connectors.policy",
        "..enterprise_connectors.registry", "..enterprise_connectors.service",
        "..enterprise_connectors.synthetic"}),
    "execution_types.py": frozenset({"dataclasses", "datetime", "typing", "types", "uuid", ".models", "..enterprise_connectors.registry"}),
    "gateway.py": frozenset({"time", "uuid", ".execution_types", ".fake_model", ".models", ".policy",
                             "..enterprise_connectors.models", "..enterprise_connectors.registry"}),
    "fake_model.py": frozenset({".execution_types"}),
    "sqlite_ledger.py": frozenset({"contextlib", "dataclasses", "datetime", "hashlib", "os", "pathlib", "sqlite3", "stat", "threading",
                                  "uuid", "msvcrt", ".execution_types", ".models", "..enterprise_connectors.models"}),
}
FILESYSTEM_CALLS = frozenset({"open", "read_text", "read_bytes", "write_text", "write_bytes", "mkdir", "unlink",
                             "rmdir", "chmod", "stat", "lstat", "resolve", "exists", "is_file", "is_dir"})


def assert_module(name, source):
    assert name in C01 | C02
    tree = ast.parse(source)
    if name in C01:
        _assert_c01_pure_ast(tree)
        return tree
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(alias.name in IMPORTS[name] for alias in node.names)
        if isinstance(node, ast.ImportFrom):
            assert "." * node.level + node.module in IMPORTS[name]
        if isinstance(node, ast.Call):
            call = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", None)
            assert call not in {"__import__", "eval", "exec", "_validate_delivery", "_event", "generate_summary",
                                "add_api_route", "api_route", "include_router", "system", "popen", "clear_frames"}
            if name != "sqlite_ledger.py":
                connector_read = (name == "source_boundary.py" and call == "execute"
                                  and ast.unparse(node.func) == "self._service.execute")
                if not connector_read:
                    assert call not in FILESYSTEM_CALLS | {"connect", "execute", "executemany", "executescript", "cursor"}
            if call == "invoke":
                rendered = ast.unparse(node.func)
                assert ((name == "gateway.py" and rendered == "self.model.invoke")
                        or (name == "orchestration.py" and rendered == "compiled.invoke"))
            if call == "_extract":
                assert name == "fake_model.py" and ast.unparse(node.func) == "self._extract"
        if isinstance(node, ast.Attribute): assert node.attr not in {"f_locals", "f_globals", "gi_frame", "cr_frame"}
        if isinstance(node, ast.Name): assert node.id != "__builtins__"
        if name != "sqlite_ledger.py" and isinstance(node, ast.Constant) and type(node.value) is str and node.value.strip():
            assert node.value.lstrip().split(None, 1)[0].upper() not in {
                "SELECT", "INSERT", "UPDATE", "DELETE", "CREATE", "ALTER", "DROP", "PRAGMA", "ATTACH"}
    return tree


def assert_acyclic(graph):
    done, active = set(), set()
    def visit(name):
        assert name not in active, "Circular C01/C02 dependency"
        if name in done: return
        active.add(name)
        for dependency in graph[name]: visit(dependency)
        active.remove(name)
        done.add(name)
    for name in graph: visit(name)


def assert_no_wiring(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all("enterprise_ai_processing" not in a.name for a in node.names)
        if isinstance(node, ast.ImportFrom): assert "enterprise_ai_processing" not in (node.module or "")
        if isinstance(node, ast.Constant) and type(node.value) is str:
            assert "enterprise_ai_processing" not in node.value


def test_closed_inventory_imports_effects_and_no_cycles():
    package = ROOT / "enterprise_ai_processing"
    assert {str(p.relative_to(package)).replace("\\", "/") for p in package.rglob("*.py")} == C01 | C02
    graph = {}
    for name in C01 | C02:
        tree = assert_module(name, (package / name).read_text(encoding="utf-8"))
        graph[name] = {node.module + ".py" for node in ast.walk(tree)
                       if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module + ".py" in C01 | C02}
    assert_acyclic(graph)


def test_no_application_clinical_or_old_connector_workflow_wiring():
    for path in ROOT.rglob("*.py"):
        if "enterprise_ai_processing" not in path.relative_to(ROOT).parts:
            assert_no_wiring(ast.parse(path.read_text(encoding="utf-8")))


@pytest.mark.parametrize("source", ["import sqlite3", "import socket", "import httpx", "import openai",
    "from azure import identity", "import langgraph", "from app.config import Settings",
    "from app.human_review import Case", "import google.genai", "from .sqlite_ledger import Ledger",
    "engine.invoke()", "store.execute('SELECT x')", "open('file')", "service._validate_delivery()",
    "service._event()", "__import__('socket')", "x='SELECT x FROM y'"])
def test_c01_negative_controls_still_reject_original_forbidden_dependencies(source):
    with pytest.raises(AssertionError):
        _assert_c01_pure_ast(ast.parse(source))


@pytest.mark.parametrize("name,source", [("gateway.py", "import sqlite3"), ("gateway.py", "from pathlib import Path"),
    ("gateway.py", "connection.execute('SELECT x')"), ("fake_model.py", "import sqlite3"),
    ("fake_model.py", "from app.config import Settings"), ("execution_types.py", "import socket"),
    ("sqlite_ledger.py", "import httpx"), ("sqlite_ledger.py", "import openai"),
    ("sqlite_ledger.py", "import fcntl"),
    ("gateway.py", "from app.gemini_provider import GeminiProvider"), ("gateway.py", "import mcp"),
    ("gateway.py", "from app.institutional_knowledge import index"), ("gateway.py", "router.add_api_route()"),
    ("gateway.py", "service._event()"), ("sqlite_ledger.py", "service._validate_delivery()"),
    ("execution_types.py", "model.invoke()"), ("gateway.py", "model._extract()"),
    ("unexpected.py", "pass"),     ("source_boundary.py", "cursor.execute('SELECT x')"),
    ("source_boundary.py", "service._event()"), ("grounding.py", "cursor.execute('SELECT x')"),
    ("answer.py", "cursor.execute('SELECT x')"), ("authorization.py", "import socket"),
    ("delivery_sink.py", "open('file')"), ("orchestration.py", "self.model.invoke()"),
    ("composition.py", "service.execute()"), ("composition.py", "import openai"),
    ("gateway.py", "open('file')"), ("gateway.py", "frame.f_locals"),
    ("gateway.py", "traceback.clear_frames(tb)"), ("fake_model.py", "__builtins__['eval']('x')")])
def test_c02_negative_architecture_controls(name, source):
    with pytest.raises(AssertionError):
        assert_module(name, source)


def test_negative_cycle_and_endpoint_wiring_controls():
    with pytest.raises(AssertionError):
        assert_acyclic({"gateway.py":{"fake_model.py"}, "fake_model.py":{"gateway.py"}})
    with pytest.raises(AssertionError):
        assert_no_wiring(ast.parse("from app.enterprise_ai_processing.gateway import Gateway"))
