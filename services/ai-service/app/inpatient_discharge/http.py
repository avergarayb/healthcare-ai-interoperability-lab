"""Service routes for discharge preparation. The browser does not supply the chart."""
import json
import os
from json import JSONDecodeError

from fastapi.responses import JSONResponse

from app.service_auth import authenticate

from .graph import BlockedTransport, DischargeGraph, InterceptedTransport, fetch_chart
from .store import audit, authorize, decide

_DECISIONS = {"approved", "rejected", "changes_requested"}


def prepare_discharge(request, settings, raw, fetcher=None):
    if not authenticate(request, settings):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    body = _body(raw)
    if body is None:
        return JSONResponse({"error": "invalid_input"}, status_code=400)
    graph = DischargeGraph(_review_path(), _transport(), fetcher or _fetcher())
    try:
        result = graph.invoke(body)
    except Exception:
        return JSONResponse({"error": "unavailable", "closesEncounter": False}, status_code=503)
    status = 200 if result.get("phase") in {"PENDING_REVIEW", "PENDING_INFORMATION", "DENIED", "FAILED"} else 503
    return JSONResponse(result, status_code=status)


def decide_discharge(request, settings, raw, fetcher=None):
    if not authenticate(request, settings):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    body = _body(raw)
    if body is None or body.get("decision") not in _DECISIONS:
        return JSONResponse({"outcome": "invalid_approval", "episodeClosed": False}, status_code=400)
    try:
        chart = (fetcher or _fetcher())(body.get("episodeId"))
    except Exception:
        return JSONResponse({"outcome": "source_unavailable", "episodeClosed": False}, status_code=503)
    if not isinstance(chart, dict):
        return JSONResponse({"outcome": "source_unavailable", "episodeClosed": False}, status_code=503)
    result = decide(
        _review_path(), body.get("proposalId"), body.get("proposalHash"), body.get("episodeVersion"),
        body.get("decision"), body.get("actorId"), body.get("organizationId"), body.get("idempotencyKey"),
        chart.get("version"))
    return JSONResponse(result)


def authorize_follow_ups(request, settings, raw, fetcher=None):
    if not authenticate(request, settings):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    body = _body(raw)
    if body is None:
        return JSONResponse({"outcome": "invalid_approval"}, status_code=400)
    try:
        chart = (fetcher or _fetcher())(body.get("episodeId"))
    except Exception:
        return JSONResponse({"outcome": "source_unavailable"}, status_code=503)
    result = authorize(
        _review_path(), body.get("proposalId"), body.get("proposalHash"),
        body.get("actorId"), body.get("organizationId"), chart)
    return JSONResponse(result)


def discharge_audit(request, settings, proposal_id):
    if not authenticate(request, settings):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    return JSONResponse({"events": audit(_review_path(), proposal_id), "closesEncounter": False})


def _body(raw):
    try:
        body = json.loads(raw)
    except (JSONDecodeError, TypeError):
        return None
    return body if type(body) is dict else None


def _review_path():
    return os.environ.get("DISCHARGE_REVIEW_DB", "data/discharge-review.sqlite3")


def _transport():
    return InterceptedTransport() if os.environ.get("DISCHARGE_MODEL_MODE") == "intercepted" else BlockedTransport()


def _fetcher():
    base = os.environ.get("MINI_HIS_BASE_URL", "")
    token = os.environ.get("MINI_HIS_INPATIENT_TOKEN", "")

    def fetch(episode_id):
        return fetch_chart(base, token, episode_id)

    return fetch
