"""Operational demonstration commands. check does not start Docker."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "ai-service"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from demo_profile import (  # noqa: E402
    AI_PORT,
    CONTAINER,
    FHIR_PORT,
    HIS_PORT,
    LIS_PORT,
    POSTGRES_PORT,
    assert_profile_is_isolated,
    check_dependencies,
)
from demo_runner import DemoFailure, execute, stop_current  # noqa: E402


def main(argv: list[str]) -> int:
    command = argv[1] if len(argv) > 1 else "check"
    if command == "check":
        assert_profile_is_isolated()
        missing = check_dependencies()
        print("profile=end-to-end-demo-operational-v1")
        print(f"ports his={HIS_PORT} lis={LIS_PORT} fhir={FHIR_PORT} ai={AI_PORT} postgres={POSTGRES_PORT}")
        print(f"container={CONTAINER}")
        print("hapi=not-started")
        print("docker-required-for-run=mini-lis-postgresql")
        if missing:
            print("missing=" + ",".join(missing))
            return 1
        print("dependencies=present")
        return 0
    if command == "stop":
        stop_current()
        print("stopped")
        return 0
    if command == "run":
        keep = "--keep" in argv
        try:
            report = execute(keep=keep)
        except DemoFailure as exc:
            print(f"demo_failed={exc.code}")
            return 1
        print(f"execution={report['executionId']}")
        print(f"review={report['reviewUrl']}")
        for item in report["scenarios"]:
            print(
                f"{item['scenario']} evaluation={item['evaluationStatus']} "
                f"langgraph={item['langGraphStatus']} case={item['reviewCaseId']}"
            )
        return 0
    print("usage: run_demo.py check|run [--keep]|stop")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
