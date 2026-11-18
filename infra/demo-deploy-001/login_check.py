"""One real authorization-code login. Prints statuses only, never secrets."""
from __future__ import annotations

import json
import os
import socket
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import httpx

_ORIGINAL = socket.getaddrinfo
_NAMES = {"demo.localhost", "pe.demo.localhost", "es.demo.localhost"}


def _resolve(host, port, *args, **kwargs):
    if host in _NAMES:
        host = "127.0.0.1"
    return _ORIGINAL(host, port, *args, **kwargs)


socket.getaddrinfo = _resolve


class _Forms(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.forms: list[dict] = []
        self._current: dict | None = None

    def handle_starttag(self, tag, attrs) -> None:
        data = dict(attrs)
        if tag == "form":
            self._current = {"action": data.get("action", ""), "inputs": {}}
            self.forms.append(self._current)
        elif tag == "input" and self._current is not None and data.get("name"):
            self._current["inputs"][data["name"]] = data.get("value", "")


def _form(html: str, required: str) -> dict | None:
    parser = _Forms()
    parser.feed(html)
    for form in parser.forms:
        if required in form["inputs"]:
            return form
    return None


def _cookie_secure(response: httpx.Response, name: str) -> bool:
    for header in response.headers.get_list("set-cookie"):
        if header.startswith(name + "="):
            lowered = header.lower()
            return "secure" in lowered and "httponly" in lowered
    return False


def _login(http: httpx.Client, username: str, password: str) -> dict:
    start = http.post(
        "https://pe.demo.localhost:18443/lab-review-iam/start",
        headers={"Origin": "https://pe.demo.localhost:18443"},
        follow_redirects=False,
    )
    if start.status_code != 303:
        return {"user": username, "outcome": "start_rejected", "status": start.status_code}
    page = http.get(start.headers["location"], follow_redirects=True)
    form = _form(page.text, "username")
    if form is None:
        return {"user": username, "outcome": "form_rejected", "status": page.status_code}
    form["inputs"]["username"] = username
    form["inputs"]["password"] = password
    posted = http.post(urljoin(str(page.url), form["action"]), data=form["inputs"], follow_redirects=True)
    callback = _form(posted.text, "code")
    if callback is None:
        return {"user": username, "outcome": "callback_form_rejected", "status": posted.status_code}
    finished = http.post(
        urljoin(str(posted.url), callback["action"]), data=callback["inputs"], follow_redirects=False)
    tray = http.get("https://pe.demo.localhost:18443/lab-summaries")
    return {
        "user": username,
        "outcome": "session" if finished.status_code == 303 and urlsplit(finished.headers.get("location", "")).path == "/lab-summaries" and _cookie_secure(finished, "lab_review_iam") else "session_rejected",
        "callback": finished.status_code,
        "tray": tray.status_code,
        "session_cookie_secure": _cookie_secure(finished, "lab_review_iam"),
        "location_path": urlsplit(finished.headers.get("location", "")).path,
    }


def main() -> None:
    run = Path(os.environ["DEMO_RUN_DIR"])
    passwords = json.loads((run / "user-passwords.json").read_text(encoding="utf-8"))
    report = []
    with httpx.Client(verify=str(run / "certs" / "ca.crt"), timeout=20.0, follow_redirects=False) as http:
        for username in ("reviewer-pe", "auditor-pe", "reviewer-other"):
            report.append(_login(http, username, passwords[username]))
            http.cookies.clear()
        reviewer = httpx.Client(verify=str(run / "certs" / "ca.crt"), timeout=20.0, follow_redirects=False)
        try:
            signed = _login(reviewer, "reviewer-pe", passwords["reviewer-pe"])
            page = reviewer.get("https://pe.demo.localhost:18443/lab-summaries")
            form = _form(page.text, "csrf")
            logout = None
            if form is not None:
                logout = reviewer.post(
                    "https://pe.demo.localhost:18443/lab-review-iam/logout",
                    data={"csrf": form["inputs"]["csrf"]},
                    headers={"Origin": "https://pe.demo.localhost:18443"},
                )
            report.append({
                "user": "reviewer-pe-logout",
                "outcome": "signed_out" if logout is not None and logout.status_code == 303 else "logout_rejected",
                "status": None if logout is None else logout.status_code,
                "session": signed["outcome"],
            })
        finally:
            reviewer.close()
    passed = all(item["outcome"] in {"session", "signed_out"} for item in report)
    print(json.dumps({"outcome": "passed" if passed else "failed", "checks": report}))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as error:
        print(json.dumps({"outcome": "failed", "reason": type(error).__name__}))
        raise SystemExit(1) from None
