"""Local demonstration boundary. These tests do not start Docker or a provider."""
import importlib
import json
import sqlite3
import sys
from pathlib import Path

import pytest

from app.clinical_federation_client import ClinicalFederationClient
from app.jurisdiction_lab.mcp_tool import _client_allowed as jurisdiction_allowed
from app.jurisdiction_lab.profile import PERU, SPAIN
from app.lab_federation_hosts import federation_host_allowed
from app.longitudinal_lab.mcp_tool import _client_allowed as longitudinal_allowed
from app.longitudinal_lab.policy import request_real_provider_send
from app.enterprise_llm_providers.errors import ProviderError


ROOT = Path(__file__).resolve().parents[3]
PLATFORM = ROOT / "infra" / "platform-001"
sys.path.insert(0, str(PLATFORM))
profiles = importlib.import_module("profiles")
prepare = importlib.import_module("prepare")
sqlite_backup = importlib.import_module("sqlite_backup")


def _client(base_url, profile):
    return ClinicalFederationClient(
        base_url, "lab-token", organization_id="org-mini-his",
        patient_system_key="mini-his", patient_identifier_system=profile.patient_system,
        sources=(profile.source_key,))


def test_docker_hosts_stay_bound_to_one_source():
    assert federation_host_allowed("federation-pe", "pe-lab-demo")
    assert federation_host_allowed("127.0.0.1", "es-lab-demo")
    assert not federation_host_allowed("federation-pe", "es-lab-demo")
    assert not federation_host_allowed("federation-es", "pe-lab-demo")
    assert not federation_host_allowed("generativelanguage.googleapis.com", "pe-lab-demo")
    assert not federation_host_allowed("federation-pe.example", "pe-lab-demo")
    peru = _client("http://federation-pe:8081", PERU)
    spain_on_peru = _client("http://federation-pe:8081", SPAIN)
    assert longitudinal_allowed(peru, PERU)
    assert jurisdiction_allowed(peru, PERU)
    assert not longitudinal_allowed(spain_on_peru, SPAIN)
    assert not jurisdiction_allowed(_client("http://evil.example", PERU), PERU)


def test_profile_name_is_not_selectable():
    assert profiles.require_profile("pe-lab-demo-v1") == "pe-lab-demo-v1"
    assert profiles.require_profile("es-lab-demo-v1") == "es-lab-demo-v1"
    with pytest.raises(ValueError):
        profiles.require_profile("peru")
    with pytest.raises(ValueError):
        profiles.require_profile("pe-lab-demo-v1,es-lab-demo-v1")


def test_real_provider_send_stays_closed():
    with pytest.raises(ProviderError) as error:
        request_real_provider_send()
    assert error.value.reason == "provider_send_blocked"


def test_prepare_writes_secrets_outside_the_repository(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("PLATFORM_RUN_DIR", str(tmp_path))
    prepare.main()
    first = (tmp_path / "federation-token").read_text(encoding="utf-8")
    prepare.main()
    assert (tmp_path / "federation-token").read_text(encoding="utf-8") == first
    realm = json.loads((tmp_path / "realm.json").read_text(encoding="utf-8"))
    assert realm["realm"] == "platform-001"
    assert realm["realm"] != "lab-review-iam"
    assert realm["clients"][0]["directAccessGrantsEnabled"] is False
    assert {item["username"] for item in realm["users"]} == {
        "reviewer-pe", "auditor-pe", "reviewer-es", "reviewer-other"}
    bindings = json.loads((tmp_path / "bindings.json").read_text(encoding="utf-8"))
    assert bindings["issuer"] == profiles.ISSUER
    printed = capsys.readouterr().out
    assert first not in printed
    assert "AIza" not in json.dumps(realm)


def test_backup_round_trip_keeps_the_schema_version(tmp_path):
    source = tmp_path / "ledger.sqlite"
    connection = sqlite3.connect(source)
    connection.execute("CREATE TABLE aip_store (singleton INTEGER PRIMARY KEY, schema_version INTEGER)")
    connection.execute("INSERT INTO aip_store (singleton, schema_version) VALUES (1, 9)")
    connection.commit()
    connection.close()
    copied = sqlite_backup.copy_sqlite(source, tmp_path / "isolated")
    assert sqlite_backup.schema_version(copied) == 9
    with pytest.raises(ValueError):
        sqlite_backup.copy_sqlite(source, source.parent)
    empty = tmp_path / "empty.sqlite"
    sqlite3.connect(empty).close()
    with pytest.raises(sqlite3.OperationalError):
        sqlite_backup.schema_version(sqlite_backup.copy_sqlite(empty, tmp_path / "missing"))


def test_compose_keeps_the_demo_closed():
    text = (PLATFORM / "compose.yaml").read_text(encoding="utf-8")
    assert "internal: true" not in text
    assert "127.0.0.1:" in text
    assert "0.0.0.0:" not in text
    assert "GEMINI_API_KEY" not in text
    assert "hapi-fhir-postgres-data" not in text
    assert "mini-lis-postgres-data" not in text
    assert "/realms/lab-review-iam" not in text
    assert "condition: service_healthy" in text
    assert "federation-pe:8081" in text
    assert "federation-es:8081" in text
    assert "pe-lab-demo-v1" in text
    assert "es-lab-demo-v1" in text
    down = (PLATFORM / "down.ps1").read_text(encoding="utf-8")
    clean = (PLATFORM / "clean.ps1").read_text(encoding="utf-8")
    assert "-v" not in down
    assert "volume rm" not in down
    assert "platform-001_" in clean
    assert "$Confirm" in clean
    entry = (ROOT / "services" / "fhir-integration-service" / "docker" / "entrypoint.sh").read_text(encoding="utf-8")
    assert "echo \"$FEDERATION_MINI_HIS_TOKEN\"" not in entry
    assert "/usr/sbin/ip route del default" in entry
    assert '"/usr/sbin/ip", "route", "del", "default"' in (ROOT / "services" / "ai-service" / "docker" / "entrypoint.py").read_text(encoding="utf-8")
    assert "cap_add: [NET_ADMIN]" in text
    ai = (ROOT / "services" / "ai-service" / "docker" / "entrypoint.py").read_text(encoding="utf-8")
    assert "GEMINI_API_KEY" in ai
    assert "print(os.environ" not in ai
