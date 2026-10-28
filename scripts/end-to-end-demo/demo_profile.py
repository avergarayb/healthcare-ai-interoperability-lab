"""Isolated ports and commands for the operational cross-organization demonstration.

The profile does not start processes. It does not change clinical-read.source.
"""

from __future__ import annotations

import shutil
from pathlib import Path


RESERVED_PORTS = frozenset({8080, 8081, 8090, 8095, 8096, 18181, 18195, 18196, 15433})
HIS_PORT = 18295
LIS_PORT = 18296
FHIR_PORT = 18281
AI_PORT = 18290
POSTGRES_PORT = 15434
CONTAINER = "e2e-demo-pg"
ORGANIZATION_ID = "org-mini-his"
POSITIVE_PATIENT = "MHS-PAT-002"
POSITIVE_ENCOUNTER = "MHS-CON-002"
NEGATIVE_PATIENT = "MHS-PAT-003"
NEGATIVE_ENCOUNTER = "MHS-CON-003"
LIS_TOKEN = "lis-federation-token"
HIS_EXCHANGE_TOKEN = "his-federation-exchange"
HIS_FEDERATION_TOKEN = "his-federation-read"
AI_SERVICE_TOKEN = "e2e-demo-ai-service"
PROTOCOL_ID = "CROSS_ORG_LAB_RESULT_REVIEW_V1"
WORKFLOW_TYPE = "cross_org_lab_result"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def runtime_root() -> Path:
    return repo_root() / "services" / "ai-service" / ".tmp-e2e-demo"


def check_dependencies(which=shutil.which) -> list[str]:
    """Return the names of required tools that are not on PATH. Does not start them."""
    maven = "mvn.cmd" if __import__("os").name == "nt" else "mvn"
    required = ("docker", maven, "java")
    return [name for name in required if which(name) is None]


def postgres_command() -> list[str]:
    return [
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
    ]


def fhir_arguments(exchange_db: str, his_url: str, lis_url: str) -> list[str]:
    """Spring arguments for the isolated FHIR process. The HAPI default stays untouched."""
    federation_audit_db = Path(exchange_db).with_name("federation-security-audit.sqlite")
    return [
        f"--server.port={FHIR_PORT}",
        "--server.address=127.0.0.1",
        "--spring.autoconfigure.exclude=org.springframework.boot.autoconfigure.jdbc.DataSourceAutoConfiguration",
        f"--exchange.store-path={exchange_db}",
        f"--federation.security-audit.store-path={federation_audit_db.as_posix()}",
        f"--exchange.connectors.mini-lis.base-url={lis_url}",
        f"--exchange.connectors.mini-lis.service-token={LIS_TOKEN}",
        f"--exchange.participants.mini-his.service-token={HIS_EXCHANGE_TOKEN}",
        f"--exchange.participants.mini-lis.service-token={LIS_TOKEN}",
        f"--clinical-read.mini-his.base-url={his_url}",
        f"--clinical-read.mini-lis.base-url={lis_url}",
        f"--clinical-read.mini-lis.service-token={LIS_TOKEN}",
        f"--interop.sources.mini-his.base-url={his_url}",
        f"--interop.sources.mini-lis.base-url={lis_url}",
        f"--federation.participants.mini-his.service-token={HIS_FEDERATION_TOKEN}",
        "--federation.participants.mini-lis.service-token=lis-federation-read",
    ]


def assert_profile_is_isolated() -> None:
    ports = {HIS_PORT, LIS_PORT, FHIR_PORT, AI_PORT, POSTGRES_PORT}
    overlap = ports & RESERVED_PORTS
    if overlap:
        raise RuntimeError(f"demo ports overlap reserved ports: {sorted(overlap)}")
    arguments = " ".join(fhir_arguments("exchange.sqlite", "http://127.0.0.1", "http://127.0.0.1"))
    if "clinical-read.source" in arguments or "local-hapi" in arguments or "hapi" in arguments.lower():
        raise RuntimeError("the demo profile must not select or start HAPI")
