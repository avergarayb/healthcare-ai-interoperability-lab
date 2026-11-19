"""Service routes for the showcase lab summary. The browser does not call them."""
import json

from fastapi.responses import JSONResponse

from app.clinical_federation_client import FederationClientError
from app.service_auth import authenticate

from .showcase_run import (
    SummaryRejected,
    decide_case,
    federation_client,
    latest_case,
    prepare_case,
    read_case,
    replay_case,
    summary_root,
)


def prepare_summary(request, settings, raw):
    return _run(request, settings, raw, lambda body: prepare_case(
        summary_root(), federation_client(settings), body["actorId"]))


def replay_summary(request, settings, case_id, raw):
    return _run(request, settings, raw, lambda _body: replay_case(
        summary_root(), case_id, federation_client(settings)))


def decide_summary(request, settings, case_id, raw):
    return _run(request, settings, raw, lambda body: decide_case(
        summary_root(), case_id, body.get("decision")))


def read_summary(request, settings, case_id):
    if not authenticate(request, settings):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    try:
        return JSONResponse(read_case(summary_root(), case_id))
    except SummaryRejected as error:
        return JSONResponse({"error": error.reason}, status_code=error.status)


def latest_summary(request, settings):
    if not authenticate(request, settings):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    try:
        return JSONResponse(latest_case(summary_root()))
    except SummaryRejected as error:
        return JSONResponse({"error": error.reason}, status_code=error.status)


def _run(request, settings, raw, action):
    if not authenticate(request, settings):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    body = _body(raw)
    if body is None:
        return JSONResponse({"error": "invalid_input"}, status_code=400)
    denied = _guard(body)
    if denied is not None:
        return denied
    try:
        return JSONResponse(action(body))
    except SummaryRejected as error:
        return JSONResponse({"error": error.reason}, status_code=error.status)
    except FederationClientError as error:
        return JSONResponse({"error": error.code}, status_code=503)


def _guard(body):
    if body.get("role") != "clinician":
        return JSONResponse({"error": "role_denied"}, status_code=403)
    if body.get("organizationId") != "org-mini-his":
        return JSONResponse({"error": "organization_denied"}, status_code=403)
    if "actorId" in body and not isinstance(body.get("actorId"), str):
        return JSONResponse({"error": "invalid_input"}, status_code=400)
    return None


def _body(raw):
    if raw is None or len(raw) > 2000:
        return None
    if raw == b"":
        return {}
    try:
        parsed = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed
