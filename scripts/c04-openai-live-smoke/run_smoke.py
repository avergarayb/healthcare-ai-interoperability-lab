"""C04 smoke entry point. With no arguments it stays on the offline dry-run."""
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "ai-service"))

from app.enterprise_llm_providers.live_smoke import cli


if __name__ == "__main__":
    report = cli(sys.argv[1:], sys.stdin, os.environ)
    sys.exit(0 if report.get("result") == "PASS" else 2)
