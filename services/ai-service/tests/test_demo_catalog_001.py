"""Static checks for the hospital demonstration package."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
COMPOSE = ROOT / "infra" / "demo-catalog-001" / "compose.yaml"
RUNNER = ROOT / "infra" / "demo-catalog-001" / "run.ps1"


def test_hospital_compose_publishes_no_ports():
    text = COMPOSE.read_text(encoding="utf-8")
    assert "ports:" not in text
    assert "2575" in text and "8095" in text
    assert "NET_ADMIN" not in text
    assert "demo-catalog-hospital" in text
    assert "org-mini-his" not in text or "MINI_HIS" in text


def test_runner_refuses_historical_projects_and_keeps_volumes():
    text = RUNNER.read_text(encoding="utf-8")
    assert "platform-001" in text
    assert "demo-deploy-001" in text
    assert "down -v" not in text
    assert "CATALOG_EPHEMERAL" in text
    assert "yyyyMMddHHmmssfff" in text
    assert "NewGuid" in text
    assert "down -v" not in text
