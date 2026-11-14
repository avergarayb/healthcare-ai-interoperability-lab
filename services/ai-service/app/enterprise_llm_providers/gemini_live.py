"""Isolated Gemini smoke. dry-run does not send. live-once stays behind a TTY confirmation.

The public Gemini transport remains closed. This module does not import a provider SDK.
The one live dispatch, when later authorized, goes through the neutral gateway and the
existing generateContent normalizer. It is not a general egress switch.
"""
import json
import os
import sys
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path

from app.model_gateway.adapters import lab_adapters
from app.model_gateway.contracts import ExecutionContext, ExecutionGrant
from app.model_gateway.gateway import NeutralModelGateway
from app.model_gateway.policy import REQUIRED
from app.model_gateway.registry import ProviderRegistry, lab_catalog
from app.model_gateway.sdk_bridge import GeminiSdkBridge

from .errors import ProviderError
from .gemini_configuration import ALLOWED_MODEL, GeminiSettings, TIMEOUT_MILLISECONDS
from .gemini_pricing import CALL_CEILING_MICROUSD, estimate_microusd
from .gemini_request import build_generation, request_bytes, require_closed_generation
from .gemini_transport import (
    DisabledGeminiTransport, dispatch_generate, open_official_client, require_official_client,
)
from .permit import CLASSIFICATION, PURPOSE
from .schema import QUESTION_ID
from .smoke import FIXED_DOCUMENT, FIXED_ORGANIZATION, FIXED_PRINCIPAL, FIXED_RESOURCE


ATTEMPT_ID = "002"
LIVE_OUTPUT_TOKENS = 256
MARKER_NAME = "vacation-days-v1.attempt-002"
CONFIRMATION_PHRASE = (
    "CONFIRMO UNA SOLICITUD gemini gemini-3.5-flash-lite vacation-days-v1 "
    "INTENTO 002 MAXIMO USD 0.001"
)
_PLACEHOLDER = "synthetic-marker"
_REDIRECT = (
    "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy",
    "GEMINI_BASE_URL", "GOOGLE_GENAI_BASE_URL",
)
_REPORT_FIELDS = (
    "result", "reason", "mode", "provider", "model", "question_id", "requests_sent",
    "input_tokens", "output_tokens", "estimated_microusd", "reserved_microusd",
    "grounding", "project_billing", "provider_charge", "thinking_level",
    "max_output_tokens", "attempts", "timeout_milliseconds", "live_egress",
    "default_transport", "tools", "finish_reason", "candidate_present", "content_present",
    "usage_present", "candidate_tokens", "thoughts_tokens", "attempt", "cost_exact",
    "prompt_inferred", "visible_inferred", "thoughts_inferred", "tool_inferred",
)


def cli(argv, stdin, environ, clock=None):
    """Print a sanitized report. The default path does not contact Gemini."""
    selected = _clock(clock)
    try:
        mode = _mode(argv)
        if mode == "dry-run":
            report = dry_run(selected)
        else:
            report = _live_once(stdin, environ, selected)
    except ProviderError as error:
        report = _report("FAIL", error.reason, _mode_or_rejected(argv), 0, None, None, None, "FAIL")
    rendered = json.dumps(report, ensure_ascii=True, sort_keys=True)
    if _leaks(rendered, _credential(environ, "GEMINI_API_KEY")):
        report = _report("FAIL", "invalid_output", _mode_or_rejected(argv), 0, None, None, None, "FAIL")
        rendered = json.dumps(report, ensure_ascii=True, sort_keys=True)
    sys.stdout.write(rendered + "\n")
    return report


def dry_run(clock):
    """Price and ground the fixed fixture in memory. No credential and no attempt file."""
    reservation = require_ceiling(attempt_reservation())
    gateway = _gateway(_Scripted(_simulated_success()), _PLACEHOLDER, clock, reservation)
    result = gateway.execute(_context(), _grant(), None)
    _require_public(result)
    return _success(result, "dry-run", 0, reservation)


def execute_once(client, directory, clock):
    """One guarded generateContent call. Tests supply an in-process client."""
    reservation = require_ceiling(attempt_reservation())
    require_official_client(client)
    transport = FixtureTransport(client, directory)
    gateway = _gateway(transport, _PLACEHOLDER, clock, reservation)
    try:
        result = gateway.execute(_context(), _grant(), None)
    except ProviderError as error:
        return _failure(error, transport.calls, reservation)
    _require_public(result)
    return _success(result, "live-once", transport.calls, reservation)


def require_ceiling(reservation, ceiling=CALL_CEILING_MICROUSD):
    if type(reservation) is not int or reservation < 1 or reservation > ceiling:
        raise ProviderError("budget_exceeded")
    return reservation


def reject_alternate(*, document=None, model=None, base_url=None):
    if document is not None and document != FIXED_DOCUMENT:
        raise ProviderError("invalid_input")
    if model is not None and model != ALLOWED_MODEL:
        raise ProviderError("model_denied")
    if base_url is not None:
        raise ProviderError("not_configured")


def attempt_reservation():
    """Price the fixed 256-token payload. The catalog reservation stays at 128."""
    settings = GeminiSettings(
        False, ALLOWED_MODEL, 15, LIVE_OUTPUT_TOKENS, 2048, CALL_CEILING_MICROUSD, None)
    generation = build_generation(FIXED_DOCUMENT, settings)
    return estimate_microusd(request_bytes(generation), LIVE_OUTPUT_TOKENS)


def claim_attempt(directory):
    """Exclusive marker for attempt 002. It does not open the first attempt file."""
    path = Path(directory) / MARKER_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        handle = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise ProviderError("replay_denied") from None
    try:
        os.write(
            handle,
            b"provider=gemini\nmodel=gemini-3.5-flash-lite\nquestion_id=vacation-days-v1\nattempt=002\n")
    finally:
        os.close(handle)


def default_attempt_directory(environ):
    root = environ.get("LOCALAPPDATA") if isinstance(environ, Mapping) else None
    if type(root) is not str or root == "":
        raise ProviderError("not_configured")
    directory = Path(root) / "healthcare-ai-interoperability-lab" / "c04-gemini-live-smoke"
    repo = Path(__file__).resolve().parents[4]
    try:
        directory.resolve().relative_to(repo.resolve())
    except ValueError:
        return directory
    raise ProviderError("not_configured")


class FixtureTransport:
    """Sends the fixed generation once. It is not the default SDK transport."""

    def __init__(self, client, directory):
        self._client = client
        self._directory = directory
        self.calls = 0

    def send(self, generation, timeout_seconds):
        require_closed_generation(generation, FIXED_DOCUMENT)
        require_official_client(self._client)
        if timeout_seconds != 15 or self.calls:
            raise ProviderError("not_configured" if timeout_seconds != 15 else "replay_denied")
        claim_attempt(self._directory)
        self.calls += 1
        return dispatch_generate(self._client, generation)


class _Scripted:
    def __init__(self, body):
        self._body = body
        self.calls = 0

    def send(self, generation, timeout_seconds):
        require_closed_generation(generation, FIXED_DOCUMENT)
        if timeout_seconds != 15:
            raise ProviderError("not_configured")
        self.calls += 1
        body = self._body
        self._body = None
        return body


def _live_once(stdin, environ, clock):
    if not isinstance(environ, Mapping):
        raise ProviderError("invalid_input")
    if _redirect(environ) or _redirect(os.environ):
        raise ProviderError("environment_redirect")
    reservation = require_ceiling(attempt_reservation())
    credential = environ.get("GEMINI_API_KEY")
    if type(credential) is not str or credential == "":
        raise ProviderError("credential_absent")
    _require_confirmation(stdin)
    client = open_official_client(credential)
    directory = default_attempt_directory(environ)
    return _assigned(client, directory, clock, reservation)


def _assigned(client, directory, clock, reservation):
    transport = FixtureTransport(client, directory)
    gateway = _gateway(transport, _PLACEHOLDER, clock, reservation)
    try:
        result = gateway.execute(_context(), _grant(), None)
    except ProviderError as error:
        return _failure(error, transport.calls, reservation)
    _require_public(result)
    return _success(result, "live-once", transport.calls, reservation)


def _gateway(transport, credential, clock, reservation):
    settings = GeminiSettings(
        True, ALLOWED_MODEL, 15, LIVE_OUTPUT_TOKENS, 2048, CALL_CEILING_MICROUSD, credential)
    adapters = lab_adapters()
    bridge = GeminiSdkBridge(settings, transport, clock)
    if bridge.reservation() != reservation or reservation > CALL_CEILING_MICROUSD:
        raise ProviderError("budget_exceeded")
    adapters["gemini-sdk-a"] = bridge
    return NeutralModelGateway(registry=_attempt_registry(reservation), adapters=adapters)


def _attempt_registry(reservation):
    chosen = tuple(
        replace(item, reservation_microusd=reservation) if item.deployment_id == "gemini-sdk-a" else item
        for item in lab_catalog())
    return ProviderRegistry(chosen)


def _context():
    return ExecutionContext(
        FIXED_ORGANIZATION, FIXED_PRINCIPAL, FIXED_RESOURCE, PURPOSE, CLASSIFICATION,
        CALL_CEILING_MICROUSD)


def _grant():
    return ExecutionGrant(
        "gemini", "gemini-sdk-a", FIXED_ORGANIZATION, FIXED_PRINCIPAL, FIXED_RESOURCE,
        PURPOSE, CLASSIFICATION, REQUIRED, 1)


def _require_public(result):
    if hasattr(result, "days") or hasattr(result, "months") or hasattr(result, "source_excerpt"):
        raise ProviderError("invalid_output")


def _require_confirmation(stdin):
    interactive = getattr(stdin, "isatty", None)
    if not callable(interactive) or interactive() is not True:
        raise ProviderError("confirmation_required")
    sys.stderr.write(
        "Una solicitud live a gemini, modelo gemini-3.5-flash-lite, fixture vacation-days-v1, intento 002.\n"
        "Maximo una solicitud y 256 tokens de salida. Puede consumir creditos. Tope estimado USD 0.001.\n"
        "El saldo prepago no es un limite transaccional estricto.\n"
        "Escriba la frase de confirmacion:\n")
    line = stdin.readline()
    if type(line) is not str or line.strip() != CONFIRMATION_PHRASE:
        raise ProviderError("confirmation_required")


def _simulated_success():
    encoded = FIXED_DOCUMENT.encode("utf-8")
    observation = {
        "question_id": QUESTION_ID, "evidence_found": True, "proposed_days": 20, "proposed_months": 12,
        "source_excerpt": FIXED_DOCUMENT, "evidence_start": 0, "evidence_end": len(encoded),
        "refusal_or_insufficient": False,
    }
    return {
        "status": "completed",
        "output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(observation)}]}],
        "usage": {"input_tokens": 40, "output_tokens": 20},
    }


def _success(result, mode, requests_sent, reservation):
    report = _report(
        "PASS", "accepted", mode, requests_sent, result.input_tokens, result.output_tokens,
        result.estimated_microusd, "PASS", reservation)
    report.update(
        candidate_tokens=result.output_tokens, thoughts_tokens=result.thoughts_tokens,
        cost_exact=result.cost_exact, thoughts_inferred=result.thoughts_inferred,
        tool_inferred=result.tool_inferred, prompt_inferred=result.prompt_inferred,
        visible_inferred=result.visible_inferred)
    return {key: value for key, value in report.items() if key in _REPORT_FIELDS}


def _failure(error, requests_sent, reservation):
    diagnostic = getattr(error, "diagnostic", None)
    incoming = outgoing = thoughts = None
    estimated = None
    finish = candidate = content = usage_present = exact = None
    inferred = {name: None for name in (
        "prompt_inferred", "visible_inferred", "thoughts_inferred", "tool_inferred")}
    if type(diagnostic) is dict:
        incoming = diagnostic.get("input_tokens")
        outgoing = diagnostic.get("candidate_tokens")
        if type(outgoing) is not int:
            outgoing = diagnostic.get("output_tokens")
        thoughts = diagnostic.get("thoughts_tokens")
        finish = diagnostic.get("finish_reason")
        candidate = diagnostic.get("candidate_present")
        content = diagnostic.get("content_present")
        usage_present = diagnostic.get("usage_present")
        exact = diagnostic.get("cost_exact")
        inferred = {name: diagnostic.get(name) for name in (
            "prompt_inferred", "visible_inferred", "thoughts_inferred", "tool_inferred")}
        if exact is True and type(incoming) is int and type(outgoing) is int and type(thoughts) is int:
            estimated = estimate_microusd(incoming, outgoing + thoughts)
    report = _report(
        "FAIL", error.reason, "live-once", requests_sent, incoming, outgoing, estimated, "FAIL", reservation)
    report.update(
        finish_reason=finish, candidate_present=candidate, content_present=content,
        usage_present=usage_present, candidate_tokens=outgoing, thoughts_tokens=thoughts,
        cost_exact=exact, **inferred)
    return {key: value for key, value in report.items() if key in _REPORT_FIELDS}


def _report(result, reason, mode, requests_sent, input_tokens, output_tokens, estimated, grounding,
            reserved=None):
    if type(DisabledGeminiTransport()) is not DisabledGeminiTransport:
        raise ProviderError("not_configured")
    return {key: value for key, value in (
        ("result", result), ("reason", reason), ("mode", mode), ("provider", "gemini"),
        ("model", ALLOWED_MODEL), ("question_id", QUESTION_ID), ("requests_sent", requests_sent),
        ("input_tokens", input_tokens), ("output_tokens", output_tokens),
        ("estimated_microusd", estimated), ("reserved_microusd", reserved if reserved is not None else estimated),
        ("grounding", grounding), ("project_billing", "unverified"), ("provider_charge", "unconfirmed"),
        ("thinking_level", "MINIMAL"), ("max_output_tokens", LIVE_OUTPUT_TOKENS), ("attempts", 1),
        ("attempt", ATTEMPT_ID), ("candidate_tokens", None), ("thoughts_tokens", None),
        ("cost_exact", None), ("prompt_inferred", None), ("visible_inferred", None),
        ("thoughts_inferred", None), ("tool_inferred", None),
        ("timeout_milliseconds", TIMEOUT_MILLISECONDS), ("live_egress", "closed"),
        ("default_transport", "DisabledGeminiTransport"), ("tools", "absent"),
    ) if key in _REPORT_FIELDS}


def _credential(environ, name):
    if not isinstance(environ, Mapping):
        return ""
    value = environ.get(name)
    return value if type(value) is str else ""


def _redirect(environ):
    return any(environ.get(name) for name in _REDIRECT)


def _mode(argv):
    if argv in ([], ["dry-run"]):
        return "dry-run"
    if argv == ["live-once"]:
        return "live-once"
    raise ProviderError("invalid_input")


def _mode_or_rejected(argv):
    try:
        return _mode(argv)
    except ProviderError:
        return "rejected"


def _clock(clock):
    if clock is None:
        from datetime import datetime, timezone
        return lambda: datetime.now(timezone.utc)
    if not callable(clock):
        raise ProviderError("invalid_input")
    return clock


def _leaks(rendered, credential):
    if "VACACIONES" in rendered or "AIza" in rendered or "GEMINI_API_KEY" in rendered or _PLACEHOLDER in rendered:
        return True
    return type(credential) is str and credential != "" and credential in rendered
