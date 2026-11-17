"""One manual Gemini call through the neutral gateway.

Importing this module does not build a client and does not send. The command
reads the local key, asks for one confirmation, and stops after a single
attempt. A network error leaves the durable reservation held.
"""
import json
import os
import sys
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.enterprise_llm_providers.errors import ProviderError


MARKER_NAME = "egress-002.gemini.once"
AUTHORIZATION_ID = "egress-002-gemini"
_RESOURCE = "vacation-a"
_PHRASE_PROMPT = (
    "EGRESS-002: una solicitud HTTPS a gemini, modelo gemini-3.5-flash-lite, "
    "datos sinteticos vacation-days-v1.\n"
    "Maximo una solicitud. Sin reintento. El costo local no es una factura.\n"
    "Escriba la frase de confirmacion:\n"
)


def main(argv=None):
    chosen = sys.argv[1:] if argv is None else argv
    if chosen not in ([], ["once"]):
        return 2
    try:
        report = run(sys.stdin, os.environ)
    except ProviderError as error:
        sys.stdout.write(json.dumps(_failure(error, 0)) + "\n")
        return 1
    sys.stdout.write(json.dumps(report) + "\n")
    return 0 if report.get("result") == "PASS" else 1


def run(stdin, environ, clock=None):
    """Guarded entry. A non-interactive stdin never reaches the provider."""
    if not isinstance(environ, Mapping):
        raise ProviderError("invalid_input")
    _require_phrase(stdin)
    _reject_redirect(environ)
    credential = environ.get("GEMINI_API_KEY")
    if type(credential) is not str or credential == "":
        raise ProviderError("credential_absent")
    directory = _directory(environ)
    selected = clock or (lambda: datetime.now(timezone.utc))
    return _execute(directory, credential, selected)


def _require_phrase(stdin):
    interactive = getattr(stdin, "isatty", None)
    if not callable(interactive) or interactive() is not True:
        raise ProviderError("confirmation_required")
    sys.stderr.write(_PHRASE_PROMPT)
    from app.model_gateway.egress_gemini import PHRASE
    line = stdin.readline()
    if type(line) is not str or line.strip() != PHRASE:
        raise ProviderError("confirmation_required")


def _reject_redirect(environ):
    names = (
        "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy",
        "GEMINI_BASE_URL", "GOOGLE_GENAI_BASE_URL",
    )
    for name in names:
        if environ.get(name) or os.environ.get(name):
            raise ProviderError("environment_redirect")


def _directory(environ):
    root = environ.get("LOCALAPPDATA")
    if type(root) is not str or root == "":
        raise ProviderError("not_configured")
    directory = Path(root) / "healthcare-ai-interoperability-lab" / "c04-egress-002"
    repo = Path(__file__).resolve().parents[4]
    try:
        directory.resolve().relative_to(repo.resolve())
    except ValueError:
        return directory
    raise ProviderError("not_configured")


def _execute(directory, credential, clock):
    from app.enterprise_ai_processing.durable_resolver import LedgerDurableAuthorization
    from app.enterprise_ai_processing.sqlite_ledger import SQLiteExecutionLedger
    from app.model_gateway.egress_gemini import DEPLOYMENT_ID, PHRASE, OperationalGeminiConsent
    from app.model_gateway.gateway import NeutralModelGateway
    from app.model_gateway.sdk_bridge import gemini_operational_reservation

    directory.mkdir(parents=True, exist_ok=True)
    issuer = _Issuer(clock)
    admin = issuer.issue("ORG-A", "administrator")
    executor = issuer.issue("ORG-A", "executor")
    ledger = SQLiteExecutionLedger(directory, issuer, clock)
    consent = None
    fresh = not ledger.path.exists()
    try:
        _prepare(ledger, admin, executor.principal_id, clock, fresh)
        _claim_marker(directory)
        reservation = gemini_operational_reservation()
        consent = OperationalGeminiConsent.issue(
            {"GEMINI_API_KEY": credential}, authorization_id=AUTHORIZATION_ID,
            deployment_id=DEPLOYMENT_ID, organization_id="ORG-A",
            principal_id=executor.principal_id, resource_id=_RESOURCE, phrase=PHRASE,
            interactive=True, timeout_seconds=15, max_output_tokens=256)
        gateway = NeutralModelGateway(resolver=LedgerDurableAuthorization(ledger))
        try:
            result = gateway.execute(
                executor, AUTHORIZATION_ID, reservation, _RESOURCE, DEPLOYMENT_ID,
                egress_consent=consent)
        except ProviderError as error:
            report = _failure(error, consent.requests_sent, reservation)
            _write_receipt(directory, report)
            return report
        report = {
            "result": "PASS", "reason": "accepted", "provider": "gemini",
            "model": "gemini-3.5-flash-lite", "requests_sent": consent.requests_sent,
            "provider_request_id": result.provider_request_id,
            "response_status": result.response_status, "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens, "thoughts_tokens": result.thoughts_tokens,
            "reserved_microusd": result.reserved_microusd,
            "estimated_microusd": result.estimated_microusd, "cost_kind": result.cost_kind,
            "cost_exact": False, "provider_charge": "unconfirmed",
        }
        _write_receipt(directory, report)
        return report
    finally:
        ledger.close()
        admin = executor = credential = None


def _prepare(ledger, admin, principal_id, clock, fresh):
    from app.enterprise_ai_processing.execution_types import ExecutionError
    from app.enterprise_ai_processing.remote_authorization import RemoteAuthorization
    from app.model_gateway.egress_gemini import DEPLOYMENT_ID
    from app.model_gateway.sdk_bridge import gemini_operational_reservation
    ledger.initialize(admin)
    if fresh:
        ledger.migrate_to_v2(admin)
        ledger.migrate_to_v3(admin)
        ledger.migrate_to_v4(admin)
        ledger.migrate_remote_audit_v2(admin)
        ledger.migrate_to_v5(admin)
    now = clock()
    record = RemoteAuthorization(
        AUTHORIZATION_ID, "ORG-A", DEPLOYMENT_ID, "gemini", "gemini-3.5-flash-lite",
        now - timedelta(seconds=1), now + timedelta(minutes=10),
        principal_id=principal_id, resource_id=_RESOURCE,
        budget_ceiling_microusd=gemini_operational_reservation())
    try:
        ledger.register_remote_authorization(admin, record)
    except ExecutionError as error:
        if error.reason != "revision_conflict":
            raise


def _claim_marker(directory):
    path = directory / MARKER_NAME
    try:
        handle = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise ProviderError("replay_denied") from None
    try:
        os.write(handle, b"provider=gemini\nmodel=gemini-3.5-flash-lite\nquestion_id=vacation-days-v1\n")
    finally:
        os.close(handle)


def _write_receipt(directory, report):
    text = json.dumps(report, sort_keys=True)
    if "AIza" in text or "GEMINI_API_KEY" in text:
        raise ProviderError("invalid_input")
    (directory / "receipt.json").write_text(text + "\n", encoding="utf-8")


def _failure(error, requests_sent, reserved=None):
    return {
        "result": "FAIL", "reason": error.reason, "provider": "gemini",
        "model": "gemini-3.5-flash-lite", "requests_sent": requests_sent,
        "reserved_microusd": reserved, "estimated_microusd": None,
        "cost_kind": "uncertain" if requests_sent else None,
        "cost_exact": False, "provider_charge": "unconfirmed",
    }


class _Issuer:
    """Laboratory identity for this command. It is not production IAM."""

    def __init__(self, clock):
        self._clock = clock
        self._issued = {}

    def issue(self, org, role):
        from app.enterprise_ai_processing.execution_types import LaboratoryAccess
        context = LaboratoryAccess("synthetic-" + role, org, role, self._clock() + timedelta(minutes=5))
        self._issued[id(context)] = context
        return context

    def recognizes(self, context):
        return self._issued.get(id(context)) is context


if __name__ == "__main__":
    raise SystemExit(main())
