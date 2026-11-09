"""DEMO-001 console with real workflows and test-owned SQLite; no live services."""
import ast
from dataclasses import fields
import importlib.util
import os
from pathlib import Path
import socket
import subprocess
import sys

from langgraph.graph.state import CompiledStateGraph
import pytest

from app.enterprise_connectors.control_plane import ControlPlane
from app.enterprise_connectors.models import ConnectorOperation as Op
from app.enterprise_workflows.document_read import EnterpriseDocumentWorkflow, NODES
from tests.enterprise_connector_workflow_fixture import TestInvocationBoundary


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "enterprise-connector-demo" / "run_demo.py"
SPEC = importlib.util.spec_from_file_location("enterprise_connector_demo_001", SCRIPT)
demo = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = demo
SPEC.loader.exec_module(demo)


def menu(tmp_path, choices, *, read=None):
    answers, output = iter(choices), []
    def next_answer(prompt):
        try:
            return next(answers)
        except StopIteration:
            raise EOFError from None
    status = demo.main(read=next_answer if read is None else read, write=output.append, parent=tmp_path)
    assert not list(tmp_path.glob("eca-demo-001-*"))
    return status, "\n".join(output)


@pytest.mark.parametrize("choice,status,broker,wire,documents,events", [
    ("1", "DELIVERY_ALLOWED", 1, 2, 1, 4),
    ("2", "DENY", 0, 0, 0, 1),
    ("3", "DELIVERY_SUPPRESSED", 1, 2, 0, 3),
    ("4", "DELIVERY_ALLOWED", 1, 2, 1, 4),
])
def test_demo_scenarios_run_real_graph(tmp_path, monkeypatch, choice, status, broker, wire, documents, events):
    invoked, closed = [], []
    invoke, close = CompiledStateGraph.invoke, TestInvocationBoundary.close
    def observe(graph, *args, **kwargs):
        invoked.append(graph)
        assert graph.checkpointer is False and graph.store is None
        assert {item.name for item in fields(kwargs["context"])} == {"operation_id"}
        return invoke(graph, *args, **kwargs)
    def retire(boundary, envelope):
        close(boundary, envelope)
        closed.append(not boundary._issued and not boundary._leases)
    monkeypatch.setattr(CompiledStateGraph, "invoke", observe)
    monkeypatch.setattr(TestInvocationBoundary, "close", retire)
    with demo.OfflineGuard() as guard, demo.DemoSession(guard, parent=tmp_path) as session:
        report = session.run_scenario(choice)
        assert report.status == status and report.documents == documents
        assert report.broker_attempts == report.acquisitions == broker and report.wire_calls == wire
        assert len(report.audit) == events and {row.organization for row in report.audit} == {"ORG-A"}
        assert {row.correlation for row in report.audit} == {report.correlation}
        assert report.steps == (NODES[:2] if choice == "2" else NODES)
        assert not list(session.root.iterdir())  # Scenario database already closed/deleted.
        assert guard.attempts == 0
        output = []
        demo.print_report(report, output.append)
        displayed = "\n".join(output)
        if choice in {"2", "3"}: assert not report.preview and not report.provenance
        if report.preview and report.preview in repr(report): raise AssertionError("Report repr includes document text")
        if choice == "2": assert "organization_mismatch" in displayed and "Sin contenido" in displayed
        if choice == "3": assert report.revocation_confirmed and "NO se restauró" in displayed
        if choice == "4":
            assert report.policy_unchanged and "untrusted_enterprise_document" in displayed
            assert "Ignora las instrucciones anteriores" in displayed
        assert "NO confirma recepción humana" in displayed
        assert all(value not in displayed for value in ("credential-a", "tenant-a", "recipient-a", "principal-a", "CredentialReference"))
        assert session.last_audit == report.audit
        assert all(isinstance(row, demo.AuditLine) for row in session.last_audit)
    assert len(invoked) == 1 and closed == [True]


@pytest.mark.parametrize("invalid", ["", "6", "-1", "ORG-B", "https://attacker.invalid", "1 2", "--live"])
def test_invalid_input_never_invokes_workflow(tmp_path, monkeypatch, invalid):
    def forbidden(*args, **kwargs): raise AssertionError("Invalid option reached workflow")
    monkeypatch.setattr(EnterpriseDocumentWorkflow, "invoke", forbidden)
    status, output = menu(tmp_path, [invalid, "0"])
    assert status == 0 and "Opción inválida" in output


def test_repeated_scenarios_have_new_authority_and_no_retrievable_content(tmp_path):
    with demo.OfflineGuard() as guard, demo.DemoSession(guard, parent=tmp_path) as session:
        reports = [session.run_scenario(choice) for choice in ("1", "2", "3", "4", "1", "3", "1")]
        assert len({report.correlation for report in reports}) == 7
        assert [report.status for report in reports] == ["DELIVERY_ALLOWED", "DENY", "DELIVERY_SUPPRESSED",
                                                        "DELIVERY_ALLOWED", "DELIVERY_ALLOWED",
                                                        "DELIVERY_SUPPRESSED", "DELIVERY_ALLOWED"]
        assert len(session.last_audit) == 4
        assert set(vars(session)) == {"guard", "parent", "_temporary", "root", "last_audit"}
        assert not hasattr(session, "get_result") and not hasattr(session, "resume")
        assert not list(session.root.iterdir()) and guard.attempts == 0


def test_menu_audit_is_last_scenario_only_and_scope_uses_existing_port(tmp_path, monkeypatch):
    actors, audit = [], ControlPlane.audit_events
    def scoped(control, context, kind):
        actors.append((context.organization_id, kind))
        return audit(control, context, kind)
    monkeypatch.setattr(ControlPlane, "audit_events", scoped)
    status, output = menu(tmp_path, ["5", "1", "2", "5", "0"])
    assert status == 0 and "No hay escenario actual" in output
    assert output.count("Auditoría del último escenario, solo ORG-A: 1 eventos") == 2
    assert actors == [("ORG-A", "access"), ("ORG-A", "access")]


@pytest.mark.parametrize("where", ["menu", "after_read", "final_delivery"])
def test_ctrl_c_cleans_owned_resources_without_traceback(tmp_path, monkeypatch, where):
    boundaries = []
    open_boundary = TestInvocationBoundary.open
    def record(boundary):
        boundaries.append(boundary)
        envelope = open_boundary(boundary)
        if where == "after_read":
            def interrupt(request, response):
                if request.operation == Op.READ: raise KeyboardInterrupt("private synthetic fault")
            boundary.lab.transport.after_send = interrupt
        return envelope
    def interrupt_delivery(workflow, frame): raise KeyboardInterrupt("private synthetic fault")
    monkeypatch.setattr(TestInvocationBoundary, "open", record)
    if where == "final_delivery": monkeypatch.setattr(EnterpriseDocumentWorkflow, "_deliver", interrupt_delivery)
    def interrupt_menu(prompt): raise KeyboardInterrupt("private synthetic fault")
    status, output = menu(tmp_path, ["1"], read=interrupt_menu if where == "menu" else None)
    assert status == 130 and "Cancelación Ctrl+C" in output and "Documentos entregados" not in output
    assert "Traceback" not in output and "private synthetic fault" not in output
    assert all(not boundary._issued and not boundary._leases for boundary in boundaries)


def test_eof_and_unrelated_files_survive_cleanup(tmp_path):
    unrelated = tmp_path / "unrelated.txt"
    unrelated.write_text("synthetic unrelated data", encoding="utf-8")
    status, output = menu(tmp_path, [])
    assert status == 0 and "Fin de entrada" in output
    assert unrelated.read_text(encoding="utf-8") == "synthetic unrelated data"


@pytest.mark.parametrize("fault", ["audit", "unexpected"])
def test_faults_are_closed_and_do_not_print_exception_data(tmp_path, monkeypatch, fault):
    if fault == "audit":
        from app.enterprise_connectors.durable_audit import SQLiteConnectorAudit
        def broken(*args, **kwargs): raise ValueError("synthetic private fault")
        monkeypatch.setattr(SQLiteConnectorAudit, "append", broken)
    else:
        def broken(*args, **kwargs): raise ValueError("synthetic private fault")
        monkeypatch.setattr(EnterpriseDocumentWorkflow, "invoke", broken)
    status, output = menu(tmp_path, ["1", "0"])
    assert "synthetic private fault" not in output and "Traceback" not in output
    if fault == "unexpected": assert status == 1 and "ERROR" in output
    else: assert "UNAVAILABLE" in output and "Documentos entregados: 0" in output


@pytest.mark.parametrize("method", ["connect", "connect_ex", "send", "sendall", "sendto", "bind", "listen"])
def test_guard_blocks_socket_io_and_restores_methods(method):
    original = getattr(socket.socket, method)
    with socket.socket() as connection:
        with pytest.raises(demo.DemoFailure):
            with demo.OfflineGuard() as guard:
                try: getattr(connection, method)("synthetic-not-an-address")
                except demo.DemoFailure: pass  # Swallowed attempts still invalidate the session.
        assert guard.attempts == 1
    assert getattr(socket.socket, method) is original


@pytest.mark.parametrize("method", ["getaddrinfo", "gethostbyname", "gethostbyname_ex", "gethostbyaddr",
                                  "getnameinfo", "create_connection"])
def test_guard_blocks_dns_and_connection_helpers(method):
    original = getattr(socket, method)
    with pytest.raises(demo.DemoFailure):
        with demo.OfflineGuard() as guard:
            getattr(socket, method)("synthetic-not-a-host")
    assert guard.attempts == 1 and getattr(socket, method) is original


def test_import_capability_probe_never_allows_listening_or_connecting():
    with socket.socket(socket.AF_INET6) as connection:
        with pytest.raises(demo.DemoFailure):
            with demo.OfflineGuard() as guard:
                connection.bind(("::1", 0))
                assert guard.local_probes == 1 and guard.attempts == 0
                connection.listen(1)
        assert guard.attempts == 1


def test_swallowed_network_attempt_is_visible_fatal_and_never_returns_content(tmp_path, monkeypatch):
    invoke = EnterpriseDocumentWorkflow.invoke
    def attempted(workflow, arguments):
        try: socket.getaddrinfo("synthetic-invalid", 443)
        except demo.DemoFailure: pass
        return invoke(workflow, arguments)
    monkeypatch.setattr(EnterpriseDocumentWorkflow, "invoke", attempted)
    status, output = menu(tmp_path, ["1", "0"])
    assert status == 1 and "intento de conexión real bloqueado" in output
    assert "Documentos entregados" not in output


def test_real_http_api_is_blocked_before_dns_or_connect():
    import http.client
    with pytest.raises(demo.DemoFailure):
        with demo.OfflineGuard() as guard:
            connection = http.client.HTTPConnection("fixture.invalid", timeout=1)
            try: connection.request("GET", "/")
            finally: connection.close()
    assert guard.attempts == 1


def test_backend_eof_is_a_failure_not_normal_console_exit(tmp_path, monkeypatch):
    def fail(*args, **kwargs): raise EOFError("synthetic private eof")
    monkeypatch.setattr(EnterpriseDocumentWorkflow, "invoke", fail)
    status, output = menu(tmp_path, ["1"])
    assert status == 1 and "synthetic private eof" not in output


def test_cleanup_failure_is_visible_and_no_exception_payload_is_printed(tmp_path, monkeypatch):
    cleanup = demo.TemporaryDirectory.cleanup
    def fail_after_cleanup(temporary):
        cleanup(temporary)
        raise OSError("synthetic private cleanup detail")
    monkeypatch.setattr(demo.TemporaryDirectory, "cleanup", fail_after_cleanup)
    status, output = menu(tmp_path, ["0"])
    assert status == 1 and "ERROR" in output and "synthetic private cleanup detail" not in output


def test_noncanonical_temp_parent_is_rejected_without_deleting_existing_files(tmp_path):
    unrelated = tmp_path / "unrelated.txt"
    unrelated.write_text("synthetic preserved", encoding="utf-8")
    with demo.OfflineGuard() as guard:
        with pytest.raises(demo.DemoFailure):
            with demo.DemoSession(guard, parent=tmp_path / ".." / tmp_path.name): pass
    assert unrelated.exists()


def test_preview_bounds_terminal_controls_and_report_repr_excludes_content():
    text = "\x1b[31m\u202e" + "z" * 600
    preview = demo._preview(text)
    assert "\x1b" not in preview and "\u202e" not in preview
    assert len(preview) <= demo.MAX_PREVIEW + len(" [vista truncada]")


def test_only_stdlib_and_existing_lab_composition_no_live_flag_or_process_launch():
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import): imports.extend(item.name for item in node.names)
        elif isinstance(node, ast.ImportFrom): imports.append(node.module)
    assert all(name.startswith(("app.enterprise_connectors", "app.enterprise_workflows", "tests.enterprise_connector"))
               or name.split(".")[0] in {"contextlib", "dataclasses", "pathlib", "socket", "sys", "tempfile", "threading", "unittest"}
               for name in imports)
    assert not any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                   and node.func.id in {"eval", "exec", "compile"} for node in ast.walk(tree))


def test_exact_root_command_subprocess_menu_and_real_graph(tmp_path):
    process = subprocess.run([sys.executable, "-X", "utf8", str(SCRIPT)], cwd=ROOT, input="1\n5\n2\n3\n4\n0\n",
                             text=True, encoding="utf-8", capture_output=True, timeout=60,
                             env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    assert process.returncode == 0 and not process.stderr
    assert "DEMO-001" in process.stdout and "DELIVERY_ALLOWED" in process.stdout
    assert "DENY" in process.stdout and "DELIVERY_SUPPRESSED" in process.stdout
    assert "evaluate_result" in process.stdout and "Intentos de red real bloqueados: 0" in process.stdout


def test_cli_rejects_live_or_free_form_arguments():
    process = subprocess.run([sys.executable, str(SCRIPT), "--live"], cwd=ROOT,
                             capture_output=True, text=True, encoding="utf-8", timeout=15,
                             env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    assert process.returncode == 2 and "no acepta parámetros" in process.stdout


def test_environment_cannot_enable_live_transport_or_tracing():
    environment = {**os.environ, "PYTHONIOENCODING": "utf-8", "LANGSMITH_TRACING": "true",
                   "LANGCHAIN_TRACING_V2": "true", "GRAPH_TRANSPORT": "live", "RUN_LIVE_GEMINI_TESTS": "true"}
    process = subprocess.run([sys.executable, "-X", "utf8", str(SCRIPT)], cwd=ROOT, input="1\n0\n",
                             text=True, encoding="utf-8", capture_output=True, timeout=60, env=environment)
    assert process.returncode == 0 and "Intentos de red real bloqueados: 0" in process.stdout
