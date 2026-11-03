"""Explicit product startup smoke, with Keycloak absent; no clinical or provider calls."""
import json
import os
from pathlib import Path
import secrets
import subprocess
import time
import urllib.error
import urllib.request

from lab import ROOT, RUNTIME, Denied, free_port


def check(opener, url, expected):
    try:
        with opener.open(url, timeout=1) as response:
            status = response.status
    except urllib.error.HTTPError as error:
        status = error.code
    return status == expected


def main():
    workspace = ROOT.parents[1]
    java_port, python_port = 18390, 18391
    for port in (java_port, python_port, 18090):
        free_port(port)  # Refuse occupied ports; Keycloak must already have been cleaned.
    directory = RUNTIME / ("smoke-" + secrets.token_hex(8))
    directory.mkdir(parents=True, exist_ok=False)
    # No inherited application credentials, provider configuration, proxies or .env.
    environment = {k: v for k, v in os.environ.items() if k.upper() in {
        "PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "USERPROFILE", "JAVA_HOME", "COMSPEC", "PATHEXT"}}
    environment.update(PYTHONDONTWRITEBYTECODE="1", GEMINI_API_KEY="", FOLLOWUP_AGENT_ENABLED="false",
                       LLM_EXPERIMENTAL_ENABLED="false", AI_SERVICE_HOST="127.0.0.1",
                       AI_REVIEW_DB_PATH=str(directory / "review.sqlite"),
                       INSTITUTIONAL_KNOWLEDGE_DB_PATH=str(directory / "knowledge.sqlite"),
                       HUMAN_SESSION_DB_PATH=str(directory / "session.sqlite"),
                       SECURITY_AUDIT_DB_PATH=str(directory / "audit.sqlite"),
                       MODEL_BOUNDARY_BASE_URL="http://127.0.0.1:9")
    jar = workspace / "services/fhir-integration-service/target/fhir-integration-service-0.0.1-SNAPSHOT.jar"
    product_python = workspace / "services/ai-service/.venv/Scripts/python.exe"
    if not jar.is_file() or not product_python.is_file():
        raise Denied("build_and_product_environment_required")
    commands = [
        ("java", ["java", "-jar", str(jar), "--server.address=127.0.0.1", f"--server.port={java_port}",
                  "--logging.level.root=WARN", f"--exchange.store-path={directory / 'exchange.sqlite'}",
                  f"--federation.security-audit.store-path={directory / 'java-audit.sqlite'}",
                  "--fhir.servers.local-hapi.base-url=http://127.0.0.1:9/fhir"]),
        ("python", [str(product_python), "-B", "-m", "uvicorn", "app.main:app",
                    "--app-dir", str(workspace / "services/ai-service"), "--host", "127.0.0.1",
                    "--port", str(python_port), "--no-access-log", "--log-level", "warning"]),
    ]
    processes, files = [], []
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        for name, command in commands:
            output = open(directory / (name + ".log"), "x", encoding="utf-8")
            files.append(output)
            process = subprocess.Popen(command, cwd=directory, env=environment, stdout=output, stderr=output)
            processes.append(process)
        checks = [
            ("java_liveness", f"http://127.0.0.1:{java_port}/actuator/health/liveness", 200),
            ("java_legacy_gate", f"http://127.0.0.1:{java_port}/api/model-boundary/v1", 401),
            ("python_health", f"http://127.0.0.1:{python_port}/health", 200),
            ("python_legacy_gate", f"http://127.0.0.1:{python_port}/internal/agent-context", 401),
        ]
        for _ in range(60):
            if any(p.poll() is not None for p in processes):
                raise Denied("product_startup_failed")
            try:
                if all(check(opener, url, status) for _, url, status in checks):
                    evidence = {name: "PASS" for name, _, _ in checks}
                    evidence.update(keycloak="absent", clinical_calls="none", inherited_credentials="none")
                    (directory / "evidence.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
                    print(json.dumps(evidence))
                    return
            except (OSError, urllib.error.URLError):
                pass
            time.sleep(1)
        raise Denied("product_startup_timeout")
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()  # Only our recorded child PID, never existing services.
                    process.wait(timeout=10)
        for stream in files:
            stream.close()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("DENIED: product_smoke_failed; inspect ignored local logs without publishing them")
        raise SystemExit(1)
