"""Opt-in flow: PostgreSQL, Mini LIS, temporary Mini HIS, Java federation, LangGraph.

Run with RUN_FEDERATED_CONTEXT_LIVE=true. It does not use mocks for the two sources
and it does not bind 8080, 8081, 8090, 8095, or 8096.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from app.clinical_federation_client import ClinicalFederationClient
from app.config import Settings
from app.federated_clinical_context import adapt_federation_envelope
from app.followup_review import FollowUpReviewCaseService
from app.followup_review_sqlite import SQLiteFollowUpReviewCaseRepository
from app.langgraph_workflow_orchestration import GRAPH_NODES, LivePorts, SqliteCheckpointSaver, start_workflow


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_FEDERATED_CONTEXT_LIVE") != "true",
    reason="set RUN_FEDERATED_CONTEXT_LIVE=true to start the laboratory sources",
)

HIS_PORT = 18195
LIS_PORT = 18196
FHIR_PORT = 18181
POSTGRES_PORT = 15433
LIS_TOKEN = "lis-federation-token"
HIS_EXCHANGE_TOKEN = "his-federation-exchange"
HIS_FEDERATION_TOKEN = "his-federation-read"
CONTAINER = "fed-ai-context-pg"
ROOT = Path(__file__).resolve().parents[3]


def _free(port: int) -> None:
    probe = socket.socket()
    try:
        probe.bind(("127.0.0.1", port))
    except OSError as exc:
        raise RuntimeError(f"port {port} is already in use") from exc
    finally:
        probe.close()


def _wait(url: str, timeout: float = 180) -> None:
    deadline = time.time() + timeout
    last = "not started"
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status in {200, 404}:
                    return
                last = str(response.status)
        except urllib.error.HTTPError as exc:
            if exc.code in {401, 404}:
                return
            last = str(exc.code)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last = exc.__class__.__name__
        time.sleep(1)
    raise TimeoutError(f"{url} did not become ready ({last})")


def _request(url: str, token: str, body: dict | None = None, method: str | None = None) -> tuple[int, dict]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url, data=data, method=method or ("POST" if body is not None else "GET"))
    request.add_header("Accept", "application/json")
    request.add_header("X-Service-Token", token)
    if body is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = response.read()
            return response.status, json.loads(payload) if payload else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        parsed = json.loads(raw) if raw else {}
        return exc.code, parsed


def _maven(module: str, arguments: list[str], log_path: Path, env: dict[str, str]) -> subprocess.Popen:
    command = [
        "mvn.cmd" if os.name == "nt" else "mvn",
        "-q",
        "spring-boot:run",
        "-Dspring-boot.run.arguments=" + " ".join(arguments),
    ]
    log = log_path.open("w", encoding="utf-8")
    return subprocess.Popen(
        command,
        cwd=ROOT / "services" / module,
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
    )


def _stop(process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)], check=False, capture_output=True)
    else:
        process.terminate()
    try:
        process.wait(timeout=20)
    except subprocess.TimeoutExpired:
        process.kill()


def _observation_values(envelope: dict) -> set[tuple[str, str, str]]:
    found: set[tuple[str, str, str]] = set()
    for entry in envelope.get("entries") or []:
        resource = entry.get("resource") or {}
        if resource.get("resourceType") != "Observation":
            continue
        quantity = resource.get("valueQuantity") if isinstance(resource.get("valueQuantity"), dict) else {}
        value = quantity.get("value", resource.get("valueString"))
        source = ""
        meta = resource.get("meta")
        if isinstance(meta, dict) and isinstance(meta.get("source"), str):
            source = meta["source"]
        found.add((str(entry.get("sourceKey")), source, str(value)))
    return found


def test_live_java_sources_reach_langgraph(tmp_path):
    for port in (HIS_PORT, LIS_PORT, FHIR_PORT, POSTGRES_PORT):
        _free(port)
    if shutil.which("docker") is None:
        pytest.fail("docker is required for the live federated context flow")
    subprocess.run(["docker", "rm", "-f", CONTAINER], check=False, capture_output=True)
    started = subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            CONTAINER,
            "-e",
            "POSTGRES_USER=minilis",
            "-e",
            "POSTGRES_PASSWORD=minilis",
            "-e",
            "POSTGRES_DB=minilis",
            "-p",
            f"127.0.0.1:{POSTGRES_PORT}:5432",
            "postgres:16-alpine",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if started.returncode != 0:
        pytest.fail(started.stderr[-400:])
    processes: list[subprocess.Popen] = []
    try:
        _wait_tcp(POSTGRES_PORT)
        env = os.environ.copy()
        java_home = Path(r"C:\Proyectos_JAVA\jdk-21.0.2")
        if java_home.exists():
            env["JAVA_HOME"] = str(java_home)
            env["PATH"] = str(java_home / "bin") + os.pathsep + env.get("PATH", "")
        lis = _maven(
            "mini-lis-service",
            [
                f"--server.port={LIS_PORT}",
                "--server.address=127.0.0.1",
                f"--spring.datasource.url=jdbc:postgresql://127.0.0.1:{POSTGRES_PORT}/minilis",
                "--spring.datasource.username=minilis",
                "--spring.datasource.password=minilis",
                f"--mini-lis.service-token={LIS_TOKEN}",
            ],
            tmp_path / "mini-lis.log",
            env,
        )
        processes.append(lis)
        _wait(f"http://127.0.0.1:{LIS_PORT}/health")
        his_db = (tmp_path / "mini-his.sqlite").as_posix()
        his = _maven(
            "mini-his-simulator",
            [
                f"--server.port={HIS_PORT}",
                "--server.address=127.0.0.1",
                f"--mini-his.sqlite-path={his_db}",
                "--mini-his.organization-id=org-mini-his",
                f"--mini-his.exchange.base-url=http://127.0.0.1:{FHIR_PORT}",
                f"--mini-his.exchange.service-token={HIS_EXCHANGE_TOKEN}",
            ],
            tmp_path / "mini-his.log",
            env,
        )
        processes.append(his)
        _wait(f"http://127.0.0.1:{HIS_PORT}/health")
        exchange_db = (tmp_path / "exchange.sqlite").as_posix()
        fhir_env = dict(env)
        fhir_env["MODEL_BOUNDARY_SERVICE_TOKEN"] = "federation-clinical-read-test"
        fhir = _maven(
            "fhir-integration-service",
            [
                f"--server.port={FHIR_PORT}",
                "--server.address=127.0.0.1",
                "--spring.autoconfigure.exclude=org.springframework.boot.autoconfigure.jdbc.DataSourceAutoConfiguration",
                f"--exchange.store-path={exchange_db}",
                f"--exchange.connectors.mini-lis.base-url=http://127.0.0.1:{LIS_PORT}",
                f"--exchange.connectors.mini-lis.service-token={LIS_TOKEN}",
                f"--exchange.participants.mini-his.service-token={HIS_EXCHANGE_TOKEN}",
                f"--exchange.participants.mini-lis.service-token={LIS_TOKEN}",
                f"--clinical-read.mini-his.base-url=http://127.0.0.1:{HIS_PORT}",
                f"--clinical-read.mini-lis.base-url=http://127.0.0.1:{LIS_PORT}",
                f"--clinical-read.mini-lis.service-token={LIS_TOKEN}",
                f"--interop.sources.mini-his.base-url=http://127.0.0.1:{HIS_PORT}",
                f"--interop.sources.mini-lis.base-url=http://127.0.0.1:{LIS_PORT}",
                f"--federation.participants.mini-his.service-token={HIS_FEDERATION_TOKEN}",
                f"--federation.participants.mini-lis.service-token=lis-federation-read",
            ],
            tmp_path / "fhir.log",
            fhir_env,
        )
        processes.append(fhir)
        _wait(f"http://127.0.0.1:{FHIR_PORT}/actuator/health")
        status, accepted = _request(
            f"http://127.0.0.1:{FHIR_PORT}/api/exchange/v1/orders",
            HIS_EXCHANGE_TOKEN,
            {
                "sourceOrganizationId": "org-mini-his",
                "destinationSystemKey": "mini-lis",
                "externalRequestId": "FED-ORDER-AI-001",
                "testCode": "GLU",
                "testDescription": "Glucose",
                "requestedAt": "2026-03-01T10:00:00Z",
                "patient": {
                    "identifierSystem": "https://lab.local/mini-his/patient",
                    "identifierValue": "MHS-PAT-001",
                    "familyName": "Quispe",
                    "givenName": "Ana",
                    "birthDate": "1984-03-12",
                    "administrativeSex": "female",
                },
            },
        )
        assert 200 <= status < 300
        lis_order = accepted["destination"]["orderId"]
        result_status, _result = _request(
            f"http://127.0.0.1:{LIS_PORT}/orders/{lis_order}/results",
            LIS_TOKEN,
            {
                "externalResultId": "EXT-RES-FED-AI",
                "testCode": "GLU",
                "value": "141",
                "unit": "mmol/L",
                "referenceRange": "70-110",
                "resultedAt": "2026-03-01T12:00:00Z",
                "status": "FINAL",
            },
        )
        assert result_status in {200, 201}
        settings = Settings(
            model_boundary_base_url=f"http://127.0.0.1:{FHIR_PORT}",
            model_boundary_path="/api/model-boundary/v1",
            model_boundary_timeout_seconds=20,
            model_boundary_service_token="unused-read-token",
            host="127.0.0.1",
            port=8090,
            clinical_context_mode="federated",
            federation_participant_token=HIS_FEDERATION_TOKEN,
            federation_requesting_organization_id="org-mini-his",
            federation_patient_system_key="mini-his",
            federation_patient_identifier_system="https://lab.local/mini-his/patient",
            federation_sources=("mini-his", "mini-lis"),
            federation_timeout_seconds=20,
        )
        federation = ClinicalFederationClient.from_settings(settings)
        envelope = federation.query("MHS-PAT-001")
        assert envelope["status"] == "complete"
        assert {item["sourceKey"]: item["outcome"] for item in envelope["sources"]} == {
            "mini-his": "complete",
            "mini-lis": "complete",
        }
        values = _observation_values(envelope)
        assert ("mini-his", "https://lab.local/mini-his", "13.4") in values
        assert any(item[0] == "mini-lis" and item[1] == "https://lab.local/mini-lis" and "141" in item[2] for item in values)
        context, _projection = adapt_federation_envelope(envelope, "MHS-PAT-001")
        recorded = {item.recorded_value for item in context.observations}
        assert any(value and "13.4" in value for value in recorded)
        assert any(value and "141" in value for value in recorded)
        assert len(context.observations) >= 2

        class Guard:
            calls = 0

            def search(self, path: str, expected_resource_type: str):
                self.calls += 1
                raise AssertionError(path)

            def get(self, path: str):
                self.calls += 1
                raise AssertionError(path)

        guard = Guard()
        repository = SQLiteFollowUpReviewCaseRepository(tmp_path / "review.sqlite3")
        repository.initialize()
        ports = LivePorts(settings, FollowUpReviewCaseService(repository), guard, federation)
        view = start_workflow(SqliteCheckpointSaver(tmp_path / "workflow.sqlite3"), ports, "MHS-PAT-001", "post_consultation")
        assert guard.calls == 0
        assert view["status"] == "waiting_human"
        assert view["currentStep"] == "await_human"
        assert view["protocol"]["evaluationStatus"] == "matched"
        assert view["protocol"]["protocolId"] == "POST_CONSULTATION_RESULT_REVIEW_V1"
        assert "post_consultation_result_requires_review" in view["protocol"]["reasonCodes"]
        assert "Encounter/MHS-CON-001" in view["evidence"]
        assert any(item.startswith("Observation/MHS-RES-") for item in view["evidence"])
        assert "human_review" in view["steps"]
        assert "human_review" in GRAPH_NODES
        assert view["reviewCaseId"]
        case = repository.get(view["reviewCaseId"])
        assert case.narrative_text
        assert "Encounter/MHS-CON-001" in case.narrative_text
        assert "mini-lis" in case.narrative_text
        assert "decisión clínica" in case.narrative_text
        assert "Quispe" not in case.narrative_text
        rendered = json.dumps(view)
        assert "Quispe" not in rendered
        assert "13.4" in rendered
        assert "141" in rendered
        assert view["clinicalContext"]["federation"]["status"] == "complete"
        assert {item["source"] for item in view["clinicalContext"]["federation"]["resources"] if item["resourceType"] == "Observation"} == {
            "https://lab.local/mini-his",
            "https://lab.local/mini-lis",
        }

        created_status, created = _request(
            f"http://127.0.0.1:{HIS_PORT}/lab-orders",
            "",
            {
                "patientId": "MHS-PAT-001",
                "destinationSystemKey": "mini-lis",
                "testCode": "GLU",
                "testDescription": "Glucose",
                "requestedAt": "2026-03-01T10:00:00Z",
            },
        )
        assert created_status == 201
        his_order = created["orderId"]
        submitted_status, submitted = _request(
            f"http://127.0.0.1:{HIS_PORT}/lab-orders/{his_order}/submission",
            "",
            {},
        )
        assert 200 <= submitted_status < 300
        linked_lis_order = submitted["destination"]["orderId"]
        negative = start_workflow(
            SqliteCheckpointSaver(tmp_path / "cross-negative.sqlite3"),
            ports,
            "MHS-PAT-001",
            "cross_org_lab_result",
        )
        assert negative["status"] == "completed"
        assert negative["protocol"]["evaluationStatus"] == "not_matched"
        assert "result_order_mismatch" in negative["protocol"]["reasonCodes"]
        assert negative["protocol"]["protocolId"] == "CROSS_ORG_LAB_RESULT_REVIEW_V1"
        assert "await_human" not in negative["steps"]
        assert not negative.get("reviewCaseId")
        final_status, _final = _request(
            f"http://127.0.0.1:{LIS_PORT}/orders/{linked_lis_order}/results",
            LIS_TOKEN,
            {
                "externalResultId": "EXT-RES-CROSS-ORG",
                "testCode": "GLU",
                "value": "141",
                "unit": "mmol/L",
                "referenceRange": "70-110",
                "resultedAt": "2026-03-01T12:00:00Z",
                "status": "FINAL",
            },
        )
        assert final_status in {200, 201}
        positive = start_workflow(
            SqliteCheckpointSaver(tmp_path / "cross-positive.sqlite3"),
            ports,
            "MHS-PAT-001",
            "cross_org_lab_result",
        )
        assert guard.calls == 0
        assert positive["status"] == "waiting_human"
        assert positive["currentStep"] == "await_human"
        assert positive["protocol"]["evaluationStatus"] == "matched"
        assert "Encounter/MHS-CON-001" in positive["evidence"]
        assert f"ServiceRequest/{his_order}" in positive["evidence"]
        assert f"ServiceRequest/{linked_lis_order}" in positive["evidence"]
        assert any(item.startswith("Observation/") for item in positive["evidence"])
        stored = repository.get(positive["reviewCaseId"])
        assert set(stored.matched_resources) == set(positive["evidence"])
        assert "no se interpretan" in stored.narrative_text
        assert "Quispe" not in stored.narrative_text
    except Exception:
        for name in ("mini-lis.log", "mini-his.log", "fhir.log"):
            path = tmp_path / name
            if path.exists():
                text = path.read_text(encoding="utf-8", errors="replace")
                print(name, text[-1500:])
        raise
    finally:
        for process in processes:
            _stop(process)
        subprocess.run(["docker", "rm", "-f", CONTAINER], check=False, capture_output=True)


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
    raise TimeoutError(f"127.0.0.1:{port} did not accept connections")
