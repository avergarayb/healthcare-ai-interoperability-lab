"""Run the synthetic cross-organization demonstration against real services.

Unit tests call the scenario functions with a fake client. The CLI starts
PostgreSQL because Mini LIS persists there. It does not start HAPI.
"""

from __future__ import annotations

import json
import os
import secrets
import socket
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from demo_profile import (
    AI_PORT,
    AI_SERVICE_TOKEN,
    CONTAINER,
    FHIR_PORT,
    HIS_EXCHANGE_TOKEN,
    HIS_FEDERATION_TOKEN,
    HIS_PORT,
    LIS_PORT,
    LIS_TOKEN,
    NEGATIVE_ENCOUNTER,
    NEGATIVE_PATIENT,
    ORGANIZATION_ID,
    POSITIVE_ENCOUNTER,
    POSITIVE_PATIENT,
    POSTGRES_PORT,
    PROTOCOL_ID,
    WORKFLOW_TYPE,
    assert_profile_is_isolated,
    check_dependencies,
    fhir_arguments,
    postgres_command,
    repo_root,
    runtime_root,
)


class DemoFailure(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass
class DemoIo:
    his: str
    lis: str
    fhir: str
    request: Callable[..., tuple[int, dict]]
    federation: Callable[[str], dict]
    workflow: Callable[[str], dict]
    calls: list[str] = field(default_factory=list)


def new_execution_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"E2E-{stamp}-{secrets.token_hex(3).upper()}"


def require_correlation(his_order_id: str, receipt: dict, lis_order_id: str) -> None:
    correlation = receipt.get("correlationId")
    destination = receipt.get("destination") if isinstance(receipt.get("destination"), dict) else {}
    if not isinstance(correlation, str) or not correlation:
        raise DemoFailure("correlation_missing")
    if destination.get("orderId") != lis_order_id or not lis_order_id:
        raise DemoFailure("correlation_missing")
    if not isinstance(his_order_id, str) or not his_order_id:
        raise DemoFailure("correlation_missing")


def lis_order_is_linked(envelope: dict, his_order_id: str, lis_order_id: str) -> bool:
    for entry in envelope.get("entries") or []:
        resource = entry.get("resource") if isinstance(entry, dict) else None
        if not isinstance(resource, dict) or resource.get("resourceType") != "ServiceRequest":
            continue
        if resource.get("id") != lis_order_id:
            continue
        for identifier in resource.get("identifier") or []:
            if (
                isinstance(identifier, dict)
                and identifier.get("system") == "https://lab.local/mini-lis/order"
                and identifier.get("value") == his_order_id
            ):
                return True
    return False


def run_negative(io: DemoIo, execution_id: str) -> dict:
    """Submitted HIS order whose final result belongs to a different exchange order."""
    _finished_consultation(io, NEGATIVE_PATIENT, NEGATIVE_ENCOUNTER)
    other_external = f"E2E-OTHER-{execution_id}"[-64:]
    other_status, other = io.request(
        "POST",
        f"{io.fhir}/api/exchange/v1/orders",
        HIS_EXCHANGE_TOKEN,
        _exchange_body(io, NEGATIVE_PATIENT, other_external),
    )
    if not 200 <= other_status < 300:
        raise DemoFailure("exchange_unavailable")
    other_lis = (other.get("destination") or {}).get("orderId")
    require_correlation(other_external, other, other_lis)
    result_status, _result = io.request(
        "POST",
        f"{io.lis}/orders/{other_lis}/results",
        LIS_TOKEN,
        _result_body(f"E2E-RES-{execution_id}"[-64:], "OTHER"),
    )
    if result_status not in {200, 201}:
        raise DemoFailure("result_unavailable")
    his_order, submitted, lis_order = _submit_his_order(io, NEGATIVE_PATIENT, "NEG")
    envelope = io.federation(NEGATIVE_PATIENT)
    if not lis_order_is_linked(envelope, his_order, lis_order):
        raise DemoFailure("correlation_mismatch")
    view = io.workflow(NEGATIVE_PATIENT)
    return _scenario(
        "negative",
        execution_id,
        NEGATIVE_PATIENT,
        his_order,
        lis_order,
        "final_on_other_order",
        submitted.get("correlationId"),
        envelope,
        view,
    )


def run_positive(io: DemoIo, execution_id: str) -> dict:
    _finished_consultation(io, POSITIVE_PATIENT, POSITIVE_ENCOUNTER)
    his_order, submitted, lis_order = _submit_his_order(io, POSITIVE_PATIENT, "POS")
    result_status, _result = io.request(
        "POST",
        f"{io.lis}/orders/{lis_order}/results",
        LIS_TOKEN,
        _result_body(f"E2E-FINAL-{execution_id}"[-64:], "FINAL"),
    )
    if result_status not in {200, 201}:
        raise DemoFailure("result_unavailable")
    envelope = io.federation(POSITIVE_PATIENT)
    if not lis_order_is_linked(envelope, his_order, lis_order):
        raise DemoFailure("correlation_mismatch")
    view = io.workflow(POSITIVE_PATIENT)
    return _scenario(
        "positive",
        execution_id,
        POSITIVE_PATIENT,
        his_order,
        lis_order,
        "final",
        submitted.get("correlationId"),
        envelope,
        view,
    )


def public_report(execution_id: str, scenarios: list[dict], review_url: str) -> dict:
    """Operator report. Tokens, secrets, and names are not copied."""
    return {
        "executionId": execution_id,
        "synthetic": True,
        "productionClinicalSystem": False,
        "hapiRequired": False,
        "requestingOrganizationId": ORGANIZATION_ID,
        "protocolId": PROTOCOL_ID,
        "reviewUrl": review_url,
        "scenarios": [_public_scenario(item) for item in scenarios],
    }


def review_page_has_evidence(html: str, evidence: list[str]) -> bool:
    """The open case page shows provenance and does not replace it with Clinical Read."""
    required = (
        "origen mini-his",
        "origen mini-lis",
        "no usa Clinical Read",
    )
    return all(item in html for item in evidence) and all(item in html for item in required)


def refuse_if_running(state: dict | None) -> None:
    if state and state.get("running"):
        raise DemoFailure("demo_already_running")


def release_resources(keep: bool, succeeded: bool) -> bool:
    """A failed start is cleaned up even when the operator asked to keep a successful run."""
    return not (keep and succeeded)


def stop_recorded(state: dict, killer: Callable[[int], None], remover: Callable[[str], None]) -> None:
    if state.get("container") != CONTAINER:
        raise DemoFailure("cleanup_refused")
    for pid in state.get("pids") or []:
        killer(int(pid))
    remover(CONTAINER)


def _finished_consultation(io: DemoIo, patient_id: str, encounter_id: str) -> None:
    status, body = io.request("GET", f"{io.his}/patients/{patient_id}/consultations", "")
    if status != 200 or not isinstance(body, list):
        raise DemoFailure("consultation_unavailable")
    found = [
        item
        for item in body
        if isinstance(item, dict)
        and item.get("consultationId") == encounter_id
        and item.get("patientId") == patient_id
        and item.get("status") == "completed"
        and item.get("endedAt")
    ]
    if not found:
        raise DemoFailure("finished_consultation_missing")


def _submit_his_order(io: DemoIo, patient_id: str, label: str) -> tuple[str, dict, str]:
    status, created = io.request(
        "POST",
        f"{io.his}/lab-orders",
        "",
        {
            "patientId": patient_id,
            "destinationSystemKey": "mini-lis",
            "testCode": "GLU",
            "testDescription": f"Synthetic glucose {label}",
            "requestedAt": "2026-03-01T10:00:00Z",
        },
    )
    if status != 201 or not created.get("orderId"):
        raise DemoFailure("his_order_unavailable")
    his_order = created["orderId"]
    submitted_status, submitted = io.request(
        "POST",
        f"{io.his}/lab-orders/{his_order}/submission",
        "",
        {},
    )
    if not 200 <= submitted_status < 300:
        raise DemoFailure("exchange_unavailable")
    lis_order = (submitted.get("destination") or {}).get("orderId")
    require_correlation(his_order, submitted, lis_order)
    return his_order, submitted, lis_order


def _exchange_body(io: DemoIo, patient_id: str, external_id: str) -> dict:
    status, patient = io.request("GET", f"{io.his}/patients/{patient_id}", "")
    if status != 200:
        raise DemoFailure("patient_unavailable")
    return {
        "sourceOrganizationId": ORGANIZATION_ID,
        "destinationSystemKey": "mini-lis",
        "externalRequestId": external_id,
        "testCode": "GLU",
        "testDescription": "Synthetic glucose other order",
        "requestedAt": "2026-03-01T09:00:00Z",
        "patient": {
            "identifierSystem": "https://lab.local/mini-his/patient",
            "identifierValue": patient_id,
            "familyName": patient.get("familyName"),
            "givenName": patient.get("givenName"),
            "birthDate": patient.get("birthDate"),
            "administrativeSex": patient.get("administrativeSex"),
        },
    }


def _result_body(external_result_id: str, marker: str) -> dict:
    return {
        "externalResultId": external_result_id,
        "testCode": "GLU",
        "value": "141" if marker == "FINAL" else "140",
        "unit": "mmol/L",
        "referenceRange": "70-110",
        "resultedAt": "2026-03-01T12:00:00Z",
        "status": "FINAL",
    }


def _scenario(
    name: str,
    execution_id: str,
    patient_id: str,
    his_order: str,
    lis_order: str,
    result_state: str,
    correlation_id: object,
    envelope: dict,
    view: dict,
) -> dict:
    protocol = view.get("protocol") if isinstance(view.get("protocol"), dict) else {}
    evidence = list(view.get("evidence") or [])
    return {
        "scenario": name,
        "executionId": execution_id,
        "correlationId": correlation_id,
        "patientId": patient_id,
        "requestingOrganizationId": envelope.get("requestingOrganizationId"),
        "hisOrderId": his_order,
        "lisOrderId": lis_order,
        "resultState": result_state,
        "federationStatus": envelope.get("status"),
        "protocolId": protocol.get("protocolId"),
        "evaluationStatus": protocol.get("evaluationStatus"),
        "reasonCodes": list(protocol.get("reasonCodes") or []),
        "langGraphStatus": view.get("status"),
        "currentStep": view.get("currentStep"),
        "reviewCaseId": view.get("reviewCaseId"),
        "hisEncounterId": his_encounter(patient_id),
        "evidenceProjection": _evidence_projection(view, evidence),
        "evidence": evidence,
        "provenance": _provenance(view, evidence),
    }


def his_encounter(patient_id: str) -> str | None:
    return {
        POSITIVE_PATIENT: POSITIVE_ENCOUNTER,
        NEGATIVE_PATIENT: NEGATIVE_ENCOUNTER,
    }.get(patient_id)


_PROJECTION_FIELDS = (
    "reference",
    "protocolReference",
    "resourceType",
    "status",
    "sourceKey",
    "source",
    "fullUrl",
    "identifiers",
    "related",
    "code",
    "value",
    "unit",
)


def _evidence_projection(view: dict, evidence: list[str]) -> list[dict]:
    """Safe rows already projected by federation. Names and secrets are not fields of those rows."""
    context = view.get("clinicalContext") if isinstance(view.get("clinicalContext"), dict) else {}
    federation = context.get("federation") if isinstance(context.get("federation"), dict) else {}
    rows = [
        *(federation.get("resources") if isinstance(federation.get("resources"), list) else []),
        *(federation.get("reports") if isinstance(federation.get("reports"), list) else []),
    ]
    projected = []
    for reference in evidence:
        match = next(
            (
                row
                for row in rows
                if isinstance(row, dict)
                and (row.get("protocolReference") == reference or row.get("reference") == reference)
            ),
            None,
        )
        if match is None:
            continue
        projected.append({key: match.get(key) for key in _PROJECTION_FIELDS})
    return projected


def _provenance(view: dict, evidence: list[str]) -> list[dict]:
    context = view.get("clinicalContext") if isinstance(view.get("clinicalContext"), dict) else {}
    federation = context.get("federation") if isinstance(context.get("federation"), dict) else {}
    rows = [
        *(federation.get("resources") or []),
        *(federation.get("reports") or []),
    ]
    found = []
    for reference in evidence:
        match = next(
            (
                row
                for row in rows
                if isinstance(row, dict)
                and (row.get("protocolReference") == reference or row.get("reference") == reference)
            ),
            None,
        )
        found.append(
            {
                "reference": reference,
                "sourceKey": None if match is None else match.get("sourceKey"),
                "source": None if match is None else match.get("source"),
            }
        )
    return found


def _public_scenario(item: dict) -> dict:
    kept = (
        "scenario",
        "executionId",
        "correlationId",
        "patientId",
        "requestingOrganizationId",
        "hisOrderId",
        "lisOrderId",
        "hisEncounterId",
        "resultState",
        "federationStatus",
        "protocolId",
        "evaluationStatus",
        "reasonCodes",
        "langGraphStatus",
        "currentStep",
        "reviewCaseId",
        "evidence",
        "evidenceProjection",
        "provenance",
    )
    return {key: item.get(key) for key in kept}


def http_request(url: str, token: str = "", body: dict | list | None = None, method: str | None = None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url, data=data, method=method or ("POST" if body is not None else "GET"))
    request.add_header("Accept", "application/json")
    if token:
        request.add_header("X-Service-Token", token)
    if body is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = response.read()
            parsed = json.loads(payload) if payload else {}
            return response.status, parsed
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            parsed = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            parsed = {}
        return exc.code, parsed if isinstance(parsed, (dict, list)) else {}
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise DemoFailure("service_unavailable") from exc


def build_real_io(runtime: Path) -> DemoIo:
    from app.clinical_federation_client import ClinicalFederationClient
    from app.config import Settings
    from app.followup_review import FollowUpReviewCaseService
    from app.followup_review_sqlite import SQLiteFollowUpReviewCaseRepository
    from app.langgraph_workflow_orchestration import LivePorts, SqliteCheckpointSaver, start_workflow

    settings = _ai_settings()
    federation = ClinicalFederationClient.from_settings(settings)
    repository = SQLiteFollowUpReviewCaseRepository(runtime / "review.sqlite3")
    repository.initialize()
    saver = SqliteCheckpointSaver(runtime / "agent-workflow.sqlite3")

    class Guard:
        calls = 0

        def search(self, path: str, expected_resource_type: str):
            self.calls += 1
            raise AssertionError(path)

        def get(self, path: str):
            self.calls += 1
            raise AssertionError(path)

    ports = LivePorts(settings, FollowUpReviewCaseService(repository), Guard(), federation)

    def workflow(patient_id: str) -> dict:
        before = Guard.calls
        view = start_workflow(saver, ports, patient_id, WORKFLOW_TYPE)
        if Guard.calls != before:
            raise DemoFailure("clinical_read_called")
        return view

    def request(method: str, url: str, token: str = "", body: dict | None = None):
        return http_request(url, token, body, method)

    return DemoIo(
        his=f"http://127.0.0.1:{HIS_PORT}",
        lis=f"http://127.0.0.1:{LIS_PORT}",
        fhir=f"http://127.0.0.1:{FHIR_PORT}",
        request=request,
        federation=federation.query,
        workflow=workflow,
    )


def execute(keep: bool = False) -> dict:
    """Start the isolated stack, run both scenarios, and write a redacted report."""
    assert_profile_is_isolated()
    missing = check_dependencies()
    if missing:
        raise DemoFailure("dependencies_missing")
    _ports_free()
    state_path = runtime_root() / "current.json"
    current = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else None
    refuse_if_running(current)
    execution_id = new_execution_id()
    runtime = runtime_root() / execution_id
    runtime.mkdir(parents=True)
    processes: list[subprocess.Popen] = []
    succeeded = False
    try:
        _start_postgres()
        _wait_tcp(POSTGRES_PORT)
        env = _java_env()
        processes.append(_maven("mini-lis-service", _lis_arguments(), runtime / "mini-lis.log", env))
        _wait_http(f"http://127.0.0.1:{LIS_PORT}/health")
        processes.append(_maven("mini-his-simulator", _his_arguments(runtime), runtime / "mini-his.log", env))
        _wait_http(f"http://127.0.0.1:{HIS_PORT}/health")
        fhir_env = dict(env)
        fhir_env["MODEL_BOUNDARY_SERVICE_TOKEN"] = "federation-clinical-read-test"
        processes.append(
            _maven(
                "fhir-integration-service",
                fhir_arguments(
                    (runtime / "exchange.sqlite").as_posix(),
                    f"http://127.0.0.1:{HIS_PORT}",
                    f"http://127.0.0.1:{LIS_PORT}",
                ),
                runtime / "fhir.log",
                fhir_env,
            )
        )
        _wait_http(f"http://127.0.0.1:{FHIR_PORT}/actuator/health")
        _write_secrets(runtime)
        processes.append(_ai_process(runtime))
        _wait_http(f"http://127.0.0.1:{AI_PORT}/health")
        _write_state(state_path, execution_id, processes, True)
        io = build_real_io(runtime)
        negative = run_negative(io, execution_id)
        positive = run_positive(io, execution_id)
        review_url = f"http://127.0.0.1:{AI_PORT}/review-cases/{positive['reviewCaseId']}"
        html = _open_review(runtime, review_url)
        report = public_report(execution_id, [negative, positive], review_url)
        report["reviewPage"] = "evidence-visible" if review_page_has_evidence(html, positive["evidence"]) else "evidence-missing"
        (runtime / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        (runtime / "report.md").write_text(_markdown(report), encoding="utf-8")
        if report["reviewPage"] != "evidence-visible":
            raise DemoFailure("review_evidence_missing")
        if negative.get("reviewCaseId"):
            raise DemoFailure("negative_opened_review")
        succeeded = True
        return report
    finally:
        if release_resources(keep, succeeded):
            _release(processes, state_path)


def stop_current() -> None:
    state_path = runtime_root() / "current.json"
    if not state_path.exists():
        return
    state = json.loads(state_path.read_text(encoding="utf-8"))
    stop_recorded(state, _kill_pid, lambda name: subprocess.run(["docker", "rm", "-f", name], check=False, capture_output=True))
    state["running"] = False
    state_path.write_text(json.dumps(state), encoding="utf-8")


def _ai_settings():
    from app.config import Settings

    return Settings(
        model_boundary_base_url=f"http://127.0.0.1:{FHIR_PORT}",
        model_boundary_path="/api/model-boundary/v1",
        model_boundary_timeout_seconds=20,
        model_boundary_service_token=AI_SERVICE_TOKEN,
        host="127.0.0.1",
        port=AI_PORT,
        clinical_context_mode="federated",
        federation_participant_token=HIS_FEDERATION_TOKEN,
        federation_requesting_organization_id=ORGANIZATION_ID,
        federation_patient_system_key="mini-his",
        federation_patient_identifier_system="https://lab.local/mini-his/patient",
        federation_sources=("mini-his", "mini-lis"),
        federation_timeout_seconds=20,
    )


def _ports_free() -> None:
    for port in (HIS_PORT, LIS_PORT, FHIR_PORT, AI_PORT, POSTGRES_PORT):
        probe = socket.socket()
        try:
            probe.bind(("127.0.0.1", port))
        except OSError as exc:
            raise DemoFailure("port_in_use") from exc
        finally:
            probe.close()


def _start_postgres() -> None:
    subprocess.run(["docker", "rm", "-f", CONTAINER], check=False, capture_output=True)
    started = subprocess.run(postgres_command(), check=False, capture_output=True, text=True)
    if started.returncode != 0:
        raise DemoFailure("postgres_unavailable")


def _release(processes: list[subprocess.Popen], state_path: Path) -> None:
    for process in processes:
        _stop_process(process)
    subprocess.run(["docker", "rm", "-f", CONTAINER], check=False, capture_output=True)
    if state_path.exists():
        current = json.loads(state_path.read_text(encoding="utf-8"))
        current["running"] = False
        state_path.write_text(json.dumps(current), encoding="utf-8")


def _java_env() -> dict[str, str]:
    env = _scrubbed_environment()
    java_home = Path(r"C:\Proyectos_JAVA\jdk-21.0.2")
    if java_home.exists():
        env["JAVA_HOME"] = str(java_home)
        env["PATH"] = str(java_home / "bin") + os.pathsep + env.get("PATH", "")
    return env


def _lis_arguments() -> list[str]:
    return [
        f"--server.port={LIS_PORT}",
        "--server.address=127.0.0.1",
        f"--spring.datasource.url=jdbc:postgresql://127.0.0.1:{POSTGRES_PORT}/minilis",
        "--spring.datasource.username=minilis",
        "--spring.datasource.password=minilis",
        f"--mini-lis.service-token={LIS_TOKEN}",
    ]


def _his_arguments(runtime: Path) -> list[str]:
    return [
        f"--server.port={HIS_PORT}",
        "--server.address=127.0.0.1",
        f"--mini-his.sqlite-path={(runtime / 'mini-his.sqlite').as_posix()}",
        f"--mini-his.organization-id={ORGANIZATION_ID}",
        f"--mini-his.exchange.base-url=http://127.0.0.1:{FHIR_PORT}",
        f"--mini-his.exchange.service-token={HIS_EXCHANGE_TOKEN}",
    ]


def _maven(module: str, arguments: list[str], log_path: Path, env: dict[str, str]) -> subprocess.Popen:
    command = [
        "mvn.cmd" if os.name == "nt" else "mvn",
        "-q",
        "spring-boot:run",
        "-Dspring-boot.run.arguments=" + " ".join(arguments),
    ]
    log = log_path.open("w", encoding="utf-8")
    return subprocess.Popen(command, cwd=repo_root() / "services" / module, env=env, stdout=log, stderr=subprocess.STDOUT)


def _scrubbed_environment() -> dict[str, str]:
    """Drop credentials inherited from the operator shell. The demo sets its own."""
    blocked = ("TOKEN", "SECRET", "PASSWORD", "API_KEY", "CREDENTIAL")
    return {
        key: value
        for key, value in os.environ.items()
        if not any(part in key.upper() for part in blocked)
    }


def _write_secrets(runtime: Path) -> None:
    login = runtime / "review-login.secret"
    signing = runtime / "form-signing.secret"
    login.write_text(secrets.token_hex(32), encoding="utf-8")
    signing.write_text(secrets.token_hex(32), encoding="utf-8")
    _restrict_secret(login)
    _restrict_secret(signing)


def _restrict_secret(path: Path) -> None:
    if os.name == "nt":
        user = os.environ.get("USERNAME", "")
        domain = os.environ.get("USERDOMAIN", "")
        account = f"{domain}\\{user}" if domain and user else user
        if account:
            subprocess.run(
                ["icacls", str(path), "/inheritance:r", "/grant:r", f"{account}:(R,W)"],
                check=False,
                capture_output=True,
            )
        return
    path.chmod(0o600)


def _ai_process(runtime: Path) -> subprocess.Popen:
    python = repo_root() / "services" / "ai-service" / ".venv" / "Scripts" / "python.exe"
    if not python.exists():
        python = Path(os.sys.executable)
    env = _scrubbed_environment()
    env.update(
        {
            "AI_SERVICE_HOST": "127.0.0.1",
            "AI_SERVICE_PORT": str(AI_PORT),
            "AI_CLINICAL_CONTEXT_MODE": "federated",
            "AI_FEDERATION_PARTICIPANT_TOKEN": HIS_FEDERATION_TOKEN,
            "AI_FEDERATION_REQUESTING_ORGANIZATION_ID": ORGANIZATION_ID,
            "AI_FEDERATION_PATIENT_SYSTEM_KEY": "mini-his",
            "AI_FEDERATION_PATIENT_IDENTIFIER_SYSTEM": "https://lab.local/mini-his/patient",
            "AI_FEDERATION_SOURCES": "mini-his,mini-lis",
            "MODEL_BOUNDARY_BASE_URL": f"http://127.0.0.1:{FHIR_PORT}",
            "MODEL_BOUNDARY_SERVICE_TOKEN": AI_SERVICE_TOKEN,
            "FOLLOWUP_AGENT_ENABLED": "false",
            "LLM_EXPERIMENTAL_ENABLED": "false",
            "AI_REVIEW_DB_PATH": str(runtime / "review.sqlite3"),
            "HUMAN_SESSION_DB_PATH": str(runtime / "human-session.sqlite3"),
            "INSTITUTIONAL_KNOWLEDGE_DB_PATH": str(runtime / "institutional-knowledge.sqlite3"),
            "HUMAN_REVIEW_DEVELOPMENT_AUTH_ENABLED": "true",
            "HUMAN_REVIEW_DEVELOPMENT_AUTH_SECRET": (runtime / "review-login.secret").read_text(encoding="utf-8").strip(),
            "HUMAN_REVIEW_DEVELOPMENT_PRINCIPAL_ID": "demo-operator",
            "HUMAN_REVIEW_DEVELOPMENT_PRINCIPAL_DISPLAY_NAME": "Demo Operator",
            "HUMAN_REVIEW_FORM_SIGNING_SECRET": (runtime / "form-signing.secret").read_text(encoding="utf-8").strip(),
        }
    )
    log = (runtime / "ai-service.log").open("w", encoding="utf-8")
    return subprocess.Popen(
        [str(python), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(AI_PORT)],
        cwd=repo_root() / "services" / "ai-service",
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
    )


def _open_review(runtime: Path, review_url: str) -> str:
    secret = (runtime / "review-login.secret").read_text(encoding="utf-8").strip()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())
    login = urllib.request.Request(
        f"http://127.0.0.1:{AI_PORT}/review-login",
        data=f"developmentSecret={secret}".encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": f"http://127.0.0.1:{AI_PORT}",
        },
    )
    try:
        with opener.open(login, timeout=30) as response:
            response.read()
        with opener.open(review_url, timeout=30) as response:
            return response.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise DemoFailure("review_unavailable") from exc


def _write_state(path: Path, execution_id: str, processes: list[subprocess.Popen], running: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "executionId": execution_id,
                "container": CONTAINER,
                "pids": [process.pid for process in processes],
                "running": running,
            }
        ),
        encoding="utf-8",
    )


def _markdown(report: dict) -> str:
    lines = [
        f"# Demostración {report['executionId']}",
        "",
        "Demostración sintética. No es un sistema clínico validado para producción.",
        "",
        f"Organización solicitante: `{report['requestingOrganizationId']}`",
        f"Protocolo: `{report['protocolId']}`",
        f"Human Review: {report['reviewUrl']}",
        "",
    ]
    for item in report["scenarios"]:
        lines.extend(
            [
                f"## {item['scenario']}",
                "",
                f"- Correlación: `{item['correlationId']}`",
                f"- Paciente: `{item['patientId']}`",
                f"- Orden HIS: `{item['hisOrderId']}`",
                f"- Orden LIS: `{item['lisOrderId']}`",
                f"- Resultado: `{item['resultState']}`",
                f"- Federación: `{item['federationStatus']}`",
                f"- Evaluación: `{item['evaluationStatus']}`",
                f"- LangGraph: `{item['langGraphStatus']}` / `{item['currentStep']}`",
                f"- Caso: `{item['reviewCaseId']}`",
                "",
            ]
        )
        for row in item["provenance"]:
            lines.append(f"- `{row['reference']}` origen `{row['sourceKey']}` sistema `{row['source']}`")
        lines.append("")
    return "\n".join(lines)


def _wait_tcp(port: int, timeout: float = 60) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        probe = socket.socket()
        probe.settimeout(1)
        try:
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                return
        finally:
            probe.close()
        time.sleep(1)
    raise DemoFailure("service_unavailable")


def _wait_http(url: str, timeout: float = 180) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status in {200, 404}:
                    return
        except urllib.error.HTTPError as exc:
            if exc.code in {401, 404}:
                return
        except (urllib.error.URLError, TimeoutError, OSError):
            pass
        time.sleep(1)
    raise DemoFailure("service_unavailable")


def _stop_process(process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return
    _kill_pid(process.pid)
    try:
        process.wait(timeout=20)
    except subprocess.TimeoutExpired:
        process.kill()


def _kill_pid(pid: int) -> None:
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], check=False, capture_output=True)
    else:
        os.kill(pid, 15)
