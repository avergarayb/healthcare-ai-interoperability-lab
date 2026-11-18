"""Prove container HTTP and a blocked provider socket. Prints no secrets."""
from __future__ import annotations

import json
import os
import socket
from pathlib import Path

import httpx


def _blocked() -> bool:
    probe = socket.socket()
    probe.settimeout(3)
    try:
        probe.connect(("generativelanguage.googleapis.com", 443))
    except OSError:
        return True
    finally:
        probe.close()
    return False


def main() -> None:
    if not _blocked():
        print(json.dumps({"outcome": "failed", "reason": "provider_reachable"}))
        raise SystemExit(1)
    token = Path("/run/secrets/federation_token").read_text(encoding="utf-8").strip()
    federation = os.environ["PLATFORM_FEDERATION_URL"]
    patient = os.environ["AI_FEDERATION_PATIENT_IDENTIFIER_SYSTEM"]
    source = os.environ["AI_FEDERATION_SOURCES"]
    value = "PE-PAT-001" if source == "pe-lab-demo" else "ES-PAT-001"
    body = {
        "requestingOrganizationId": "org-mini-his",
        "patient": {
            "systemKey": "mini-his",
            "identifierSystem": patient,
            "identifierValue": value,
        },
        "sources": [source],
        "resourceTypes": ["Patient", "Observation"],
        "correlationId": "FED-PLATFORM001PROBE",
    }
    with httpx.Client(timeout=20.0, follow_redirects=False) as http:
        health = http.get(federation.rstrip("/") + "/actuator/health")
        response = http.post(
            federation.rstrip("/") + "/api/clinical-federation/v1/context",
            json=body,
            headers={"Accept": "application/json", "X-Service-Token": token},
        )
        discovery = http.get(
            "http://127.0.0.1:18340/realms/platform-001/.well-known/openid-configuration")
    document = discovery.json()
    parsed = response.json()
    report = {
        "outcome": "passed" if (
            health.status_code == 200 and response.status_code == 200
            and parsed.get("status") == "complete" and parsed.get("entries")
            and discovery.status_code == 200
            and document.get("issuer") == "http://127.0.0.1:18340/realms/platform-001"
        ) else "failed",
        "health": health.status_code,
        "federation_status": response.status_code,
        "context_status": parsed.get("status"),
        "entries": len(parsed.get("entries") or []),
        "correlation": parsed.get("correlationId"),
        "issuer": document.get("issuer"),
        "provider_socket": "blocked",
    }
    print(json.dumps(report))
    if report["outcome"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
