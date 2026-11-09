"""DEMO-001: standalone TEST/LAB console, never product composition or an API."""
from contextlib import ExitStack
from dataclasses import dataclass, field
from pathlib import Path
import socket
import sys
from tempfile import TemporaryDirectory
from threading import Event, Lock
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SERVICE = ROOT / "services" / "ai-service"
RUNTIME_PARENT = ROOT / "infra" / "iam-lab" / ".runtime"
sys.path.insert(0, str(SERVICE))
MAX_PREVIEW = 320
TITLES = {"1": "Manual ficticio de vacaciones", "2": "Intento cross-organization",
          "3": "Revocación durante lectura", "4": "Política ficticia de seguridad (texto hostil)"}
MENU = """
DEMO-001 — Conectores empresariales OFFLINE / datos ficticios
1. Consultar documento autorizado.
2. Intentar acceder a un documento de otra organización.
3. Revocar permiso durante una lectura.
4. Consultar documento con instrucciones hostiles.
5. Visualizar resumen de auditoría.
0. Salir.
"""


class DemoFailure(RuntimeError):
    """Only fixed diagnostics may cross the console error boundary."""


class OfflineGuard:
    """Process-local socket guard for this sole-purpose lab process, not a sandbox."""
    def __init__(self):
        self.attempts, self.local_probes, self._lock, self._stack = 0, 0, Lock(), ExitStack()

    def _deny(self, *args, **kwargs):
        with self._lock:
            self.attempts += 1
        raise DemoFailure("Red real bloqueada")

    def __enter__(self):
        try:
            bind = socket.socket.bind
            def ipv6_probe(connection, address):
                # urllib3 imports probe IPv6 support with bind(('::1', 0)).
                # No listen/connect/send is allowed, even on loopback.
                if connection.family == socket.AF_INET6 and address == ("::1", 0):
                    self.local_probes += 1
                    return bind(connection, address)
                return self._deny()
            self._stack.enter_context(patch.object(socket.socket, "bind", ipv6_probe))
            for name in ("connect", "connect_ex", "send", "sendall", "sendto", "sendmsg", "listen"):
                if hasattr(socket.socket, name):
                    self._stack.enter_context(patch.object(socket.socket, name, self._deny))
            for name in ("create_connection", "getaddrinfo", "gethostbyname", "gethostbyname_ex",
                         "gethostbyaddr", "getnameinfo"):
                self._stack.enter_context(patch.object(socket, name, self._deny))
            return self
        except BaseException:
            self._stack.close()
            raise

    def check(self):
        if self.attempts:
            raise DemoFailure("Intento de red detectado, incluso si fue capturado")

    def __exit__(self, kind, error, traceback):
        self._stack.close()
        if kind is None:
            self.check()


@dataclass(frozen=True, slots=True)
class AuditLine:
    phase: str
    decision: str
    reason: str
    correlation: str
    organization: str


@dataclass(frozen=True, slots=True)
class DemoReport:
    title: str
    status: str
    reason: str
    correlation: str
    operation: str
    steps: tuple[str, ...]
    audit: tuple[AuditLine, ...]
    broker_attempts: int
    acquisitions: int
    wire_calls: int
    documents: int
    preview: str = field(repr=False)
    provenance: str
    policy_unchanged: bool
    revocation_confirmed: bool


def _preview(text):
    # Terminal escapes, bidi controls and arbitrary control characters are data,
    # never terminal instructions. Bound before formatting; no eval/shell/parser.
    value = "".join(char if char.isprintable() or char == "\n" else "?" for char in text[:MAX_PREVIEW])
    return value + (" [vista truncada]" if len(text) > MAX_PREVIEW else "")


def _audit_lines(lab, correlation):
    from app.enterprise_connectors.models import Outcome, Phase, Reason
    # Existing scoped administrative port, never raw SQL or an ORG-B reader.
    events = lab.persistent.control.audit_events(lab.persistent.admin_a, "access")
    lines = []
    for event in events:
        if event["organization_id"] != "ORG-A" or event["correlation_id"] != correlation:
            raise DemoFailure("Ámbito inesperado en la auditoría de la demo")
        lines.append(AuditLine(Phase(event["phase"]).value, Outcome(event["outcome"]).value,
                               Reason(event["reason"]).value, correlation, "ORG-A"))
    return tuple(lines)


def _report(lab, boundary, result, choice, unchanged, revoked):
    from app.enterprise_connectors.models import Outcome
    preview = provenance = ""
    if result.status == Outcome.DELIVERY_ALLOWED:
        if len(result.documents) != 1 or result.documents[0].organization_id != "ORG-A":
            raise DemoFailure("Salida inesperada del workflow de laboratorio")
        document = result.documents[0]
        preview = _preview(document.text)
        provenance = f"GraphReadAdapter OFFLINE / ORG-A / versión {document.version} / {document.label}"
    elif result.documents:
        raise DemoFailure("El resultado negativo no puede contener documentos")
    return DemoReport(TITLES[choice], result.status.value, result.reason.value, result.correlation_id,
                      boundary.operation.value, result.steps, _audit_lines(lab, result.correlation_id),
                      lab.credentials.attempts, lab.credentials.acquisitions, len(lab.transport.calls),
                      len(result.documents), preview, provenance, unchanged, revoked)


class DemoSession:
    """Fresh session/scenario directories; retains only last sanitized audit, no content."""
    def __init__(self, guard, *, parent=RUNTIME_PARENT):
        self.guard, self.parent = guard, Path(parent)
        self._temporary, self.root, self.last_audit = None, None, ()

    def __enter__(self):
        self.parent.mkdir(exist_ok=True)
        if self.parent != self.parent.resolve() or self.parent.is_symlink():
            raise DemoFailure("Ruta temporal no canónica")
        self._temporary = TemporaryDirectory(prefix="eca-demo-001-", dir=self.parent)
        self.root = Path(self._temporary.name)
        return self

    def __exit__(self, kind, error, traceback):
        self.last_audit = ()
        # Only the unique directory created by TemporaryDirectory is removed.
        # Store context managers close/rollback every SQLite connection first.
        if self._temporary is not None:
            self._temporary.cleanup()

    def run_scenario(self, choice):
        if choice not in TITLES or self.root is None:
            raise DemoFailure("Opción de escenario no admitida")
        self.last_audit = ()
        self.guard.check()
        with TemporaryDirectory(prefix="scenario-", dir=self.root) as directory:
            report = self._execute(Path(directory), choice)
            self.guard.check()  # Also detect attempts swallowed by lower layers.
        self.last_audit = report.audit
        return report

    def _execute(self, directory, choice):
        # The only identity factories/transports are existing TEST fixtures.
        from app.enterprise_connectors.models import ConnectorOperation as Op
        from app.enterprise_workflows.document_read import EnterpriseDocumentWorkflow
        from tests.enterprise_connector_workflow_fixture import TestInvocationBoundary, workflow_laboratory
        lab, boundary, workflow = workflow_laboratory(directory, both=True)
        revoked = Event()
        if choice == "2":
            boundary = TestInvocationBoundary(lab, suffix="b")
            boundary.context_override = lab.persistent.context("a")
            workflow = EnterpriseDocumentWorkflow(lab.service, boundary)
        elif choice == "3":
            def revoke_after_read(request, response):
                if request.operation == Op.READ:
                    lab.persistent.invoke("change_grant", "principal_grants", "principal-grant-a", enabled=False)
                    revoked.set()  # Deterministic transport hook, before delivery.
            lab.transport.after_send = revoke_after_read
        elif choice == "4":
            boundary.resource = "security-a"  # Existing synthetic hostile text.
        before = lab.persistent.store.snapshot()
        result = None
        try:
            result = workflow.invoke(boundary.arguments())
            unchanged = lab.persistent.store.snapshot() == before
            if choice == "4" and not unchanged:
                raise DemoFailure("El contenido no puede modificar la política")
            return _report(lab, boundary, result, choice, unchanged, revoked.is_set())
        finally:
            result = workflow = None
            if boundary._issued or boundary._leases or lab.adapter._exchanges or lab.credentials._authorities:
                raise DemoFailure("Recursos propios no liberados por el fixture")


def print_audit(lines, write):
    if not lines:
        write("No hay escenario actual. Seleccione 1, 2, 3 o 4 primero.")
        return
    write(f"Auditoría del último escenario, solo ORG-A: {len(lines)} eventos persistidos y proyectados.")
    for line in lines:
        write(f"Fase={line.phase} | Decisión={line.decision} | Razón={line.reason} | "
              f"Correlación={line.correlation} | Organización={line.organization}")
    write("Gate B registra decisiones; NO confirma recepción humana. La base temporal ya fue retirada.")


def print_report(report, write):
    write(f"\nEscenario: {report.title}\nEstado: {report.status}\nOrganización solicitante: ORG-A (sintética)")
    write(f"Razón cerrada: {report.reason}")
    if report.reason == "organization_mismatch":
        write("Denegado: el recurso no pertenece a la organización del solicitante.")
    write(f"Operación: {report.operation}\nCorrelation ID: {report.correlation}")
    write("Nodos LangGraph ejecutados: " + " -> ".join(report.steps))
    for phase, label in (("local_authorization", "Autorización local"),
                         ("external_execution", "Resultado externo simulado"), ("delivery", "Gate B")):
        decisions = [line.decision for line in report.audit if line.phase == phase]
        write(f"{label}: {decisions[-1] if decisions else 'No evaluado'}")
    write(f"Broker attempts: {report.broker_attempts} | Adquisiciones: {report.acquisitions} | "
          f"Solicitudes Graph simuladas: {report.wire_calls} | Documentos entregados: {report.documents}")
    if report.documents:
        write(f"Documento: {report.title}\nProcedencia: {report.provenance}")
        write("Contenido sintético autorizado (dato, NO instrucciones):")
        for line in report.preview.splitlines():
            write("  | " + line)
    else:
        write("Sin contenido documental.")
    if report.revocation_confirmed:
        write("Revocación confirmada antes de entregar; NO se restauró el permiso.")
    write(f"Política sin cambios por contenido: {'sí' if report.policy_unchanged else 'no (revocación de prueba)'}")
    write("Gate C: DENY | Gate D: DISABLED | Sin integración LLM, embeddings, RAG o MCP.")
    print_audit(report.audit, write)


def interact(session, read, write):
    while True:
        write(MENU)
        try:
            choice = read("Seleccione una opción: ").strip()
        except EOFError:
            write("Fin de entrada. Saliendo de la demo.")
            return
        session.guard.check()
        if choice == "0":
            return
        if choice == "5":
            print_audit(session.last_audit, write)
        elif choice in TITLES:
            report = session.run_scenario(choice)
            try:
                print_report(report, write)
            finally:
                report = None
        else:
            write("Opción inválida. Use únicamente 0, 1, 2, 3, 4 o 5.")


def main(*, read=None, write=None, parent=RUNTIME_PARENT):
    read, write = input if read is None else read, print if write is None else write
    guard = OfflineGuard()
    status = 0
    try:
        with guard, DemoSession(guard, parent=parent) as session:
            interact(session, read, write)
    except KeyboardInterrupt:
        write("Cancelación Ctrl+C: sin entrega posterior; cerrando recursos propios.")
        status = 130
    except Exception:
        # Never print exception text, repr, arguments, chained errors or traceback.
        write("ERROR: demo detenida de forma cerrada. Revise el venv y el runbook; no hubo fallback.")
        status = 1
    if guard.attempts:
        write("ERROR: intento de conexión real bloqueado; ejecución inválida.")
        status = 1
    write(f"Intentos de red real bloqueados: {guard.attempts}")
    write(f"Sondeos IPv6 locales sin conexión: {guard.local_probes}")
    write("Sesión finalizada. Temporales propios retirados salvo fallo de limpieza indicado arriba.")
    return status


if __name__ == "__main__":
    if len(sys.argv) != 1:
        print("DEMO-001 no acepta parámetros, URLs ni configuración de transporte.")
        raise SystemExit(2)
    raise SystemExit(main())
