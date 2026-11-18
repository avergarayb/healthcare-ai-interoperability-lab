"""Start the local IAM loopback forwarder, then the AI service.

The forwarder accepts only 127.0.0.1:18340 inside this container and copies
bytes to the Keycloak service. It does not rewrite the issuer, the signature,
or the audience. Secrets are read from files and are not printed.
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
from pathlib import Path


def _secret(name: str, variable: str) -> None:
    path = Path("/run/secrets") / name
    if not path.is_file() or path.stat().st_size == 0:
        print("platform_start service=ai outcome=missing_secret", file=sys.stderr)
        raise SystemExit(1)
    os.environ[variable] = path.read_text(encoding="utf-8").strip()


def _pipe(source: socket.socket, target: socket.socket) -> None:
    try:
        while True:
            data = source.recv(65536)
            if not data:
                break
            target.sendall(data)
    except OSError:
        pass
    finally:
        try:
            target.shutdown(socket.SHUT_WR)
        except OSError:
            pass


def _serve(client: socket.socket, upstream: tuple[str, int]) -> None:
    remote = None
    try:
        remote = socket.create_connection(upstream, timeout=5)
        left = threading.Thread(target=_pipe, args=(client, remote), daemon=True)
        right = threading.Thread(target=_pipe, args=(remote, client), daemon=True)
        left.start()
        right.start()
        left.join()
        right.join()
    except OSError:
        pass
    finally:
        client.close()
        if remote is not None:
            remote.close()


def _forward(listen_port: int, upstream: str) -> None:
    host, separator, port = upstream.partition(":")
    if not separator or not host or not port.isdigit():
        print("platform_start service=ai outcome=invalid_upstream", file=sys.stderr)
        raise SystemExit(1)
    target = (host, int(port))
    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", listen_port))
    server.listen(32)

    def accept() -> None:
        while True:
            try:
                client, _address = server.accept()
            except OSError:
                return
            threading.Thread(target=_serve, args=(client, target), daemon=True).start()

    threading.Thread(target=accept, daemon=True).start()


def main() -> None:
    subprocess.run(["/usr/sbin/ip", "route", "del", "default"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for directory in (
        "/var/lab/review",
        "/var/lab/ledger",
        "/var/lab/iam",
        "/var/lab/human",
        "/var/lab/followup",
        "/var/lab/knowledge",
        "/var/lab/backup",
    ):
        Path(directory).mkdir(parents=True, exist_ok=True)
    _secret("federation_token", "AI_FEDERATION_PARTICIPANT_TOKEN")
    _secret("boundary_token", "MODEL_BOUNDARY_SERVICE_TOKEN")
    _secret("signing_secret", "HUMAN_REVIEW_FORM_SIGNING_SECRET")
    os.environ.pop("GEMINI_API_KEY", None)
    os.environ.pop("OPENAI_API_KEY", None)
    ca = Path(os.environ.get("DEMO_CA_FILE", ""))
    if ca.is_file():
        os.environ["SSL_CERT_FILE"] = str(ca)
        os.environ["REQUESTS_CA_BUNDLE"] = str(ca)
    upstream = os.environ.get("PLATFORM_IAM_UPSTREAM", "").strip()
    if upstream:
        _forward(int(os.environ.get("PLATFORM_IAM_LISTEN", "18340")), upstream)
    profile = os.environ.get("PLATFORM_PROFILE", "unset")
    print(f"platform_start service=ai profile={profile} iam=enabled", flush=True)
    import uvicorn
    if os.environ.get("DEMO_TRUST_PROXY") == "true":
        uvicorn.run(
            "app.main:app", host="0.0.0.0", port=8090, access_log=False,
            proxy_headers=True, forwarded_allow_ips=os.environ.get("DEMO_FORWARDED_ALLOW_IPS", "*"))
        return
    uvicorn.run("app.main:app", host="0.0.0.0", port=8090, access_log=False)


if __name__ == "__main__":
    main()
