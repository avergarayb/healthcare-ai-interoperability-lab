"""Check the local HTTPS proxy. Does not print passwords, codes, or cookies."""
from __future__ import annotations

import json
import os
import socket
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx

_ORIGINAL_GETADDRINFO = socket.getaddrinfo
_LOCAL_NAMES = {"demo.localhost", "pe.demo.localhost", "es.demo.localhost"}


def _resolve_local(host, port, *args, **kwargs):
    if host in _LOCAL_NAMES:
        host = "127.0.0.1"
    return _ORIGINAL_GETADDRINFO(host, port, *args, **kwargs)


socket.getaddrinfo = _resolve_local


def main() -> None:
    run = Path(os.environ["DEMO_RUN_DIR"])
    ca = run / "certs" / "ca.crt"
    issuer = "https://demo.localhost:18443/realms/demo-deploy"
    with httpx.Client(verify=str(ca), timeout=20.0, follow_redirects=False) as http:
        plain = http.get("http://pe.demo.localhost:18080/health")
        secure = http.get("https://pe.demo.localhost:18443/health")
        admin = http.get("https://demo.localhost:18443/admin")
        discovery = http.get(issuer + "/.well-known/openid-configuration")
        login = http.post(
            "https://pe.demo.localhost:18443/lab-review-iam/start",
            headers={"Origin": "https://pe.demo.localhost:18443"},
        )
    location = login.headers.get("location", "")
    query = parse_qs(urlsplit(location).query)
    cookie = login.headers.get("set-cookie", "")
    document = discovery.json()
    code_methods = document.get("code_challenge_methods_supported") or []
    report = {
        "http_status": plain.status_code,
        "https_redirect": plain.headers.get("location", "").startswith("https://pe.demo.localhost:18443/"),
        "health": secure.status_code,
        "admin": admin.status_code,
        "issuer": document.get("issuer"),
        "pkce": "S256" in code_methods and query.get("code_challenge_method") == ["S256"],
        "transaction_cookie_secure": "Secure" in cookie and "HttpOnly" in cookie and "samesite=none" in cookie.lower(),
        "login_status": login.status_code,
    }
    report["outcome"] = "passed" if (
        plain.status_code in {301, 308}
        and plain.headers.get("location", "").startswith("https://pe.demo.localhost:18443/")
        and secure.status_code == 200
        and admin.status_code == 404
        and document.get("issuer") == issuer
        and report["pkce"]
        and report["transaction_cookie_secure"]
        and login.status_code == 303
    ) else "failed"
    print(json.dumps(report))
    if report["outcome"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(json.dumps({"outcome": "failed", "reason": type(error).__name__}))
        raise SystemExit(1) from None
