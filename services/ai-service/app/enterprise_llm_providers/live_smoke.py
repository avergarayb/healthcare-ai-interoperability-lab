"""Isolated smoke executor for one fixed synthetic fixture.

The default mode does not open a socket. live-once stops before the SDK.
The operational send is the neutral gateway with one execution consent.
"""
import json
import os
import sys
from collections.abc import Mapping
from datetime import timedelta
from pathlib import Path

from .adapter import OpenAIResponsesAdapter
from .configuration import ALLOWED_MODEL, ProviderSettings
from .errors import ProviderError
from .permit import CLASSIFICATION, PURPOSE, RemoteExecutionPermit, SyntheticRead, permit_matches
from .pricing import estimate_microusd
from .request import build_payload
from .schema import QUESTION_ID
from .smoke import (
    FIXED_DOCUMENT, FIXED_INSTANCE, FIXED_ORGANIZATION, FIXED_PRINCIPAL, FIXED_RESOURCE,
)
from .transport import (
    TIMEOUT_SECONDS, DisabledOpenAITransport, dispatch_responses, live_egress_enabled,
    open_official_client, require_closed_payload,
)
from .validation import check_observation, parse_output, usage_tokens


MARKER_NAME = "vacation-days-v1.openai.attempt"
CONFIRMATION_PHRASE = (
    "CONFIRMO UNA SOLICITUD openai gpt-6-luna vacation-days-v1 "
    "MAXIMO USD 0.001 PRESUPUESTO PLANIFICADO USD 5"
)
CALL_CEILING_MICROUSD = 1000
LABORATORY_CAP_MICROUSD = 5_000_000
_CREDENTIAL_MARKER = "credential-marker"
_ENVIRONMENT = (
    "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy",
    "OPENAI_BASE_URL", "OPENAI_CUSTOM_HEADERS",
)
_REPORT_FIELDS = (
    "result", "reason", "mode", "provider", "model", "question_id", "requests_sent",
    "input_tokens", "output_tokens", "estimated_microusd", "reserved_microusd",
    "grounding", "project_billing", "provider_charge", "store", "service_tier",
    "reasoning_effort", "max_output_tokens", "max_retries", "timeout_seconds",
    "live_egress", "default_transport", "tools", "stream", "background",
    "observed_days", "observed_months", "response_status", "http_status",
    "incomplete_reason", "output_present", "usage_present", "reasoning_tokens",
    "total_tokens", "cost_exact", "offsets_origin",
)


def cli(argv, stdin, environ, clock=None):
    """Run dry-run or the gated live-once path and print only the sanitized report."""
    selected = _clock(clock)
    try:
        mode = _mode(argv)
        if mode == "dry-run":
            report = dry_run(selected)
        else:
            report = _live_once(stdin, environ, selected)
    except ProviderError as error:
        report = _report(result="FAIL", reason=error.reason, mode=_mode_or_rejected(argv), requests_sent=0)
    rendered = json.dumps(report, ensure_ascii=True, sort_keys=True)
    if _leaks(rendered):
        report = _report(result="FAIL", reason="invalid_output", mode=_mode_or_rejected(argv), requests_sent=0)
        rendered = json.dumps(report, ensure_ascii=True, sort_keys=True)
    sys.stdout.write(rendered + "\n")
    return report


def dry_run(clock):
    """Validate, price, and ground the fixed fixture through the simulated transport."""
    payload, reservation = prepare_fixed(clock)
    parsed = parse_output(_simulated_success())
    checked = check_observation(FIXED_DOCUMENT.encode("utf-8"), parsed)
    return _closed_report(
        "PASS", "accepted", "dry-run", 0, reservation, "encontrado", checked, None, None)


def prepare_fixed(clock, *, call_ceiling=CALL_CEILING_MICROUSD):
    """Build the only authorized payload. This does not send it."""
    now = _clock(clock)()
    settings = ProviderSettings(
        True, ALLOWED_MODEL, int(TIMEOUT_SECONDS), 256, 2048,
        CALL_CEILING_MICROUSD, LABORATORY_CAP_MICROUSD, _CREDENTIAL_MARKER)
    reading = _reading()
    if not permit_matches(_permit(now), reading, now):
        raise ProviderError("remote_not_authorized")
    payload = build_payload(FIXED_DOCUMENT, settings)
    require_closed_payload(payload, TIMEOUT_SECONDS)
    _require_fixed_payload(payload)
    reservation = _reservation(payload)
    if reservation > call_ceiling or reservation > LABORATORY_CAP_MICROUSD:
        raise ProviderError("budget_exceeded")
    return payload, reservation


def reject_alternate(*, document=None, model=None, base_url=None):
    """Refuse any fixture, model, or endpoint other than the fixed smoke."""
    if document is not None and document != FIXED_DOCUMENT:
        raise ProviderError("invalid_input")
    if model is not None and model != ALLOWED_MODEL:
        raise ProviderError("model_denied")
    if base_url is not None:
        raise ProviderError("not_configured")


def dispatch_guarded(client, payload, attempt_directory):
    """Send the fixed payload once. The neutral gateway is not used here.

    OpenAI reasoning tokens are already inside output_tokens. The shared bridge
    adds Gemini thought tokens to the billed output, so this isolated dispatch
    keeps that addition from being applied to Luna.
    """
    require_closed_payload(payload, TIMEOUT_SECONDS)
    _require_fixed_payload(payload)
    if getattr(client, "max_retries", None) != 0 or _host(getattr(client, "base_url", None)) != "api.openai.com":
        raise ProviderError("not_configured")
    reservation = _reservation(payload)
    if reservation > CALL_CEILING_MICROUSD:
        raise ProviderError("budget_exceeded")
    claim_attempt(attempt_directory)
    body = dispatch_responses(client, payload, TIMEOUT_SECONDS)
    return _from_body(body, reservation, requests_sent=1)


def claim_attempt(directory):
    """Create the one-shot marker exclusively. Failure leaves the marker in place."""
    path = Path(directory) / MARKER_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        handle = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise ProviderError("replay_denied") from None
    try:
        os.write(handle, b"provider=openai\nmodel=gpt-6-luna\nquestion_id=vacation-days-v1\n")
    finally:
        os.close(handle)


def ground(source, body):
    """Local grounding only. It does not send and does not choose a model."""
    if type(source) is not bytes:
        raise ProviderError("invalid_input")
    try:
        source.decode("utf-8")
    except UnicodeError:
        raise ProviderError("invalid_input") from None
    return check_observation(source, parse_output(body))


def default_attempt_directory(environ):
    root = environ.get("LOCALAPPDATA") if isinstance(environ, Mapping) else None
    if type(root) is not str or root == "":
        raise ProviderError("not_configured")
    directory = Path(root) / "healthcare-ai-interoperability-lab" / "c04-live-smoke"
    repo = Path(__file__).resolve().parents[4]
    try:
        directory.resolve().relative_to(repo.resolve())
    except ValueError:
        return directory
    raise ProviderError("not_configured")


def _live_once(stdin, environ, clock):
    if not isinstance(environ, Mapping):
        raise ProviderError("invalid_input")
    if _environment_redirect(environ) or _environment_redirect(os.environ):
        raise ProviderError("environment_redirect")
    prepare_fixed(clock)
    credential = environ.get("OPENAI_API_KEY")
    if type(credential) is not str or credential == "":
        raise ProviderError("credential_absent")
    _require_confirmation(stdin)
    raise ProviderError("egress_blocked")


def _require_confirmation(stdin):
    interactive = getattr(stdin, "isatty", None)
    if not callable(interactive) or interactive() is not True:
        raise ProviderError("confirmation_required")
    sys.stderr.write(
        "Una solicitud live a openai, modelo gpt-6-luna, fixture vacation-days-v1.\n"
        "Maximo una solicitud. Puede consumir creditos. Tope estimado USD 0.001.\n"
        "El tope de laboratorio USD 5 no esta verificado en el proveedor.\n"
        "Escriba la frase de confirmacion:\n")
    line = stdin.readline()
    if type(line) is not str or line.strip() != CONFIRMATION_PHRASE:
        raise ProviderError("confirmation_required")


def _from_body(body, reservation, requests_sent):
    diagnostic = _body_diagnostic(body)
    try:
        parsed = parse_output(body)
        checked = check_observation(FIXED_DOCUMENT.encode("utf-8"), parsed)
    except ProviderError as error:
        raise ProviderError(error.reason, diagnostic) from None
    usage = usage_tokens(body)
    if usage is None or diagnostic.get("cost_exact") is not True:
        raise ProviderError("consumption_ambiguous", diagnostic)
    cost = estimate_microusd(usage[0], usage[1], ceiling=False)
    report = _closed_report(
        "PASS", "accepted", "live-once", requests_sent, reservation, "encontrado",
        checked, usage[0], usage[1], estimated=cost)
    report.update(
        response_status="completed", output_present=True, usage_present=True,
        reasoning_tokens=diagnostic.get("reasoning_tokens"),
        total_tokens=diagnostic.get("total_tokens"), cost_exact=True)
    return {key: report[key] for key in _REPORT_FIELDS}


def _failure_report(error, requests_sent, reservation):
    diagnostic = getattr(error, "diagnostic", None)
    incoming = outgoing = reasoning = total = http_status = None
    status = incomplete = None
    output_present = usage_present = exact = None
    estimated = None
    if type(diagnostic) is dict:
        incoming = diagnostic.get("input_tokens")
        outgoing = diagnostic.get("output_tokens")
        reasoning = diagnostic.get("reasoning_tokens")
        total = diagnostic.get("total_tokens")
        http_status = diagnostic.get("http_status")
        status = diagnostic.get("response_status")
        incomplete = diagnostic.get("incomplete_reason")
        output_present = diagnostic.get("output_present")
        usage_present = diagnostic.get("usage_present")
        exact = diagnostic.get("cost_exact")
        if exact is True and type(incoming) is int and type(outgoing) is int:
            estimated = estimate_microusd(incoming, outgoing, ceiling=False)
    report = _report(
        result="FAIL", reason=error.reason, mode="live-once", requests_sent=requests_sent,
        input_tokens=incoming, output_tokens=outgoing, estimated_microusd=estimated,
        reserved_microusd=reservation, grounding=_label(error.reason),
        observed_days=None, observed_months=None, response_status=status,
        http_status=http_status, incomplete_reason=incomplete, output_present=output_present,
        usage_present=usage_present, reasoning_tokens=reasoning, total_tokens=total,
        cost_exact=exact)
    return report


def _body_diagnostic(body):
    usage = body.get("usage") if type(body) is dict else None
    if type(usage) is not dict:
        return {
            "response_status": body.get("status") if type(body) is dict else "absent",
            "usage_present": False, "cost_exact": False, "output_present": False,
        }
    return {
        "finish_reason": "absent",
        "response_status": body.get("status") if type(body.get("status")) is str else "absent",
        "incomplete_reason": "absent",
        "output_present": True,
        "usage_present": True,
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "reasoning_tokens": usage.get("reasoning_tokens"),
        "total_tokens": usage.get("total_tokens"),
        "cost_exact": usage.get("cost_exact") is True,
    }


def _closed_report(result, reason, mode, requests_sent, reservation, grounding, checked,
                   input_tokens, output_tokens, estimated=None):
    if live_egress_enabled() is not False:
        raise ProviderError("egress_blocked")
    if type(OpenAIResponsesAdapter()._transport) is not DisabledOpenAITransport:
        raise ProviderError("not_configured")
    return _report(
        result=result, reason=reason, mode=mode, requests_sent=requests_sent,
        input_tokens=input_tokens, output_tokens=output_tokens,
        estimated_microusd=reservation if estimated is None else estimated,
        reserved_microusd=reservation, grounding=grounding,
        observed_days=None if checked is None else checked.days,
        observed_months=None if checked is None else checked.months,
        offsets_origin=None if checked is None else checked.offsets_origin)


def _report(**fields):
    defaults = dict(
        provider="openai", model=ALLOWED_MODEL, question_id=QUESTION_ID,
        project_billing="unverified", provider_charge="unconfirmed", store=False,
        service_tier="default", reasoning_effort="none", max_output_tokens=256,
        max_retries=0, timeout_seconds=15, live_egress="closed",
        default_transport="DisabledOpenAITransport", tools="absent", stream=False, background=False,
        response_status=None, http_status=None, incomplete_reason=None, output_present=None,
        usage_present=None, reasoning_tokens=None, total_tokens=None, cost_exact=None,
        offsets_origin=None)
    for key, value in defaults.items():
        fields.setdefault(key, value)
    return {key: fields.get(key) for key in _REPORT_FIELDS}


def _simulated_success():
    encoded = FIXED_DOCUMENT.encode("utf-8")
    observation = {
        "question_id": QUESTION_ID, "evidence_found": True, "proposed_days": 20, "proposed_months": 12,
        "source_excerpt": FIXED_DOCUMENT, "evidence_start": 0, "evidence_end": len(encoded),
        "refusal_or_insufficient": False,
    }
    return {
        "status": "completed", "model": ALLOWED_MODEL,
        "output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(observation)}]}],
        "usage": {"input_tokens": 32, "output_tokens": 16},
    }


def _reading():
    return SyntheticRead(
        FIXED_ORGANIZATION, FIXED_PRINCIPAL, FIXED_INSTANCE, FIXED_RESOURCE,
        PURPOSE, CLASSIFICATION, QUESTION_ID, FIXED_DOCUMENT.encode("utf-8"))


def _permit(now):
    return RemoteExecutionPermit(
        FIXED_ORGANIZATION, FIXED_PRINCIPAL, FIXED_INSTANCE, FIXED_RESOURCE,
        PURPOSE, CLASSIFICATION, "openai", ALLOWED_MODEL, QUESTION_ID, 1,
        now - timedelta(minutes=1), now + timedelta(minutes=5), True)


def _require_fixed_payload(payload):
    content = payload.get("input", [{}])[0].get("content", "")
    if type(content) is not str or content.count(FIXED_DOCUMENT) != 1 or "tools" in payload:
        raise ProviderError("invalid_input")
    if _CREDENTIAL_MARKER in content or payload.get("model") != ALLOWED_MODEL:
        raise ProviderError("invalid_input")


def _reservation(payload):
    return estimate_microusd(
        len(json.dumps(payload).encode("utf-8")), payload["max_output_tokens"], ceiling=True)


def _environment_redirect(environ):
    return any(environ.get(name) for name in _ENVIRONMENT)


def _host(url):
    return getattr(url, "host", "")


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


def _label(reason):
    if reason == "model_refusal":
        return "insuficiente"
    return "invalido"


def _leaks(rendered):
    return "VACACIONES" in rendered or "sk-" in rendered or _CREDENTIAL_MARKER in rendered
