"""Gemini dry-run. It has no live mode and accepts no document argument."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "ai-service"))

from app.enterprise_llm_providers.gemini_smoke import dry_run_fixed_fixture, simulated_success


def main(argv):
    if argv not in ([], ["dry-run"]):
        sys.stdout.write('{"result": "FAIL", "reason": "invalid_input", "requests_sent": 0}\n')
        return 2
    result = dry_run_fixed_fixture(lambda: datetime.now(timezone.utc), simulated_success())
    report = {
        "result": "PASS" if result.accepted else "FAIL",
        "reason": result.reason,
        "provider": "gemini",
        "model": "gemini-3.5-flash-lite",
        "requests_sent": 0,
        "observed_days": result.days,
        "observed_months": result.months,
        "reserved_microusd": result.reserved_microusd,
        "estimated_microusd": result.estimated_microusd,
        "provider_charge": "unconfirmed",
        "project_billing": "unverified",
    }
    rendered = json.dumps(report, ensure_ascii=True, sort_keys=True)
    if "VACACIONES" in rendered or "AIza" in rendered:
        sys.stdout.write('{"result": "FAIL", "reason": "invalid_output", "requests_sent": 0}\n')
        return 2
    sys.stdout.write(rendered + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
