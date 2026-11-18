"""Static checks for the single-VM demonstration package. They do not start Docker."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PACKAGE = ROOT / "infra" / "demo-deploy-001"


def test_compose_publishes_only_the_local_proxy():
    text = (PACKAGE / "compose.yaml").read_text(encoding="utf-8")
    assert "name: demo-deploy-001" in text
    assert "127.0.0.1:18080:18080" in text
    assert "127.0.0.1:18443:18443" in text
    assert "0.0.0.0:" not in text
    assert "8090:8090" not in text
    assert "8081:8081" not in text
    assert "5432:5432" not in text
    assert "NET_ADMIN" not in text
    assert "latest" not in text
    assert "GEMINI_API_KEY" not in text
    assert "docker.sock" not in text
    assert "KC_DB: postgres" in text
    assert "profiles: [\"peru\"]" in text
    assert "profiles: [\"spain\"]" in text
    assert "platform-001_" not in text
    assert "hapi-fhir-postgres" not in text
    caddy = (PACKAGE / "Caddyfile").read_text(encoding="utf-8")
    assert "tls internal" not in caddy
    assert "/admin*" in caddy
    assert "/realms/demo-deploy/*" in caddy
    assert "request>headers>Cookie delete" in caddy
    assert "delete code" in caddy
    example = (PACKAGE / "Caddyfile.vm.example").read_text(encoding="utf-8")
    assert "DEMO_PUBLIC_HOST" in example
    down = (PACKAGE / "down.sh").read_text(encoding="utf-8")
    assert "-v" not in down
    assert "vm_not_authorized" in (PACKAGE / "preflight.py").read_text(encoding="utf-8")
