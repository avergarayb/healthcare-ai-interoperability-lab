"""Reject an incomplete or remote configuration before Compose starts."""
from __future__ import annotations

import os
import stat
import sys
from pathlib import Path


REQUIRED = (
    "federation-token",
    "boundary-token",
    "signing-secret",
    "bootstrap-password.txt",
    "db-password.txt",
    "realm.json",
    "bindings.json",
    "user-passwords.json",
    "certs/cert.pem",
    "certs/key.pem",
    "certs/ca.crt",
)


def main() -> None:
    mode = os.environ.get("DEMO_MODE", "local")
    if mode == "vm" and os.environ.get("DEMO_VM_AUTHORIZED") != "true":
        raise SystemExit("vm_not_authorized")
    if mode == "local":
        host = os.environ.get("DEMO_PUBLIC_HOST", "demo.localhost")
        if not host.endswith(".localhost"):
            raise SystemExit("local_host_rejected")
    elif mode != "vm":
        raise SystemExit("mode_rejected")
    if os.environ.get("GEMINI_API_KEY", "").strip() or os.environ.get("OPENAI_API_KEY", "").strip():
        raise SystemExit("provider_key_present")
    raw = os.environ.get("DEMO_RUN_DIR", "")
    if not raw:
        raise SystemExit("run_directory_missing")
    run = Path(raw)
    repo = Path(__file__).resolve().parents[2]
    if not run.is_dir() or run.resolve().is_relative_to(repo.resolve()):
        raise SystemExit("run_directory_rejected")
    for name in REQUIRED:
        path = run / name
        if not path.is_file() or path.stat().st_size == 0:
            raise SystemExit("configuration_incomplete")
        if os.name == "posix":
            mode_bits = stat.S_IMODE(path.stat().st_mode)
            if mode_bits & (stat.S_IRGRP | stat.S_IROTH | stat.S_IWGRP | stat.S_IWOTH):
                raise SystemExit("permissions_rejected")
    compose = Path(__file__).with_name("compose.yaml").read_text(encoding="utf-8")
    if "latest" in compose or "GEMINI_API_KEY" in compose or "NET_ADMIN" in compose:
        raise SystemExit("compose_rejected")
    if "127.0.0.1:18080:18080" not in compose or "127.0.0.1:18443:18443" not in compose:
        raise SystemExit("compose_rejected")
    for published in ("8090:8090", "8081:8081", "5432:5432", "0.0.0.0:"):
        if published in compose:
            raise SystemExit("compose_rejected")
    print("preflight=passed mode=" + mode)


if __name__ == "__main__":
    try:
        main()
    except SystemExit as error:
        print(error.code if isinstance(error.code, str) else "preflight_failed", file=sys.stderr)
        raise
