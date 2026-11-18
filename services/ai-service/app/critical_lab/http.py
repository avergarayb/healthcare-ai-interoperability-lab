"""Service routes for critical-lab coordination. The browser does not call them."""
import json
import os
import urllib.error
import urllib.request
from json import JSONDecodeError

from fastapi.responses import JSONResponse

from app.service_auth import authenticate

from .graph import BlockedTransport, CriticalLabGraph, InterceptedTransport
from .store import apply_grant, decide

def prepare_critical(request, settings, raw, fetcher=None, path=None, on=None):
    if not authenticate(request, settings):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    body = _body(raw)
    if body is None:
        return JSONResponse({"error": "invalid_input"}, status_code=400)
    graph = CriticalLabGraph(_path(path), _transport(), fetcher or _fetcher())
    try:
        result = graph.invoke(body, on=on)
    except Exception:
        return JSONResponse({"error": "unavailable", "closesEncounter": False}, status_code=503)
    status = 200 if result.get("phase") in {"PENDING_REVIEW", "DENIED"} else 503
    return JSONResponse(result, status_code=status)


def decide_critical(request, settings, raw, path=None):
    if not authenticate(request, settings):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    body = _body(raw)
    if body is None:
        return JSONResponse({"outcome": "invalid_approval"}, status_code=400)
    result = decide(
        _path(path), body.get("proposalId"), body.get("proposalHash"), body.get("decision"),
        body.get("actorId"), body.get("organizationId"), body.get("idempotencyKey"))
    return JSONResponse(result, status_code=200 if result["outcome"] == "recorded" else 409)


def apply_critical(request, settings, raw, path=None):
    if not authenticate(request, settings):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    body = _body(raw)
    if body is None:
        return JSONResponse({"outcome": "not_approved"}, status_code=400)
    result = apply_grant(_path(path), body.get("proposalId"), body.get("proposalHash"), body.get("organizationId"))
    return JSONResponse(result, status_code=200 if result["outcome"] in {"created", "already_created"} else 409)


def _fetcher():
    base = os.environ.get("MINI_LIS_BASE_URL", "").rstrip("/")
    token = os.environ.get("MINI_LIS_SERVICE_TOKEN", "")

    def fetch(order_id):
        if not base.startswith("http://127.0.0.1:") or not token or not order_id:
            return None
        request = urllib.request.Request(
            f"{base}/orders/{order_id}/critical-event",
            headers={"X-Service-Token": token, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError):
            return None
        return payload if isinstance(payload, dict) else None

    return fetch


def _transport():
    if os.environ.get("CRITICAL_LAB_MODEL_MODE") == "intercepted":
        return InterceptedTransport()
    return BlockedTransport()


def _path(path):
    return path or os.environ.get("CRITICAL_LAB_REVIEW_DB") or os.path.join(os.environ.get("TEMP", "."), "critical-lab-review.sqlite")


def _body(raw):
    try:
        body = json.loads(raw)
    except (JSONDecodeError, TypeError):
        return None
    return body if isinstance(body, dict) else None
