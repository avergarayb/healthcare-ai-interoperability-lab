"""Manual one-shot lab summary. Importing this module does not send.

Run from services/ai-service only after a new Product Owner authorization:

    .\\.venv\\Scripts\\python.exe -m app.clinical_lab_summary.once once

Java Clinical Federation must already be running. This command does not start
Mini HIS, Mini LIS, PostgreSQL, or HAPI, and it does not retry a failed send.
"""
import json
import os
import sys
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.enterprise_llm_providers.errors import ProviderError


MARKER_NAME = "e2e-clinical-001.gemini.once"
AUTHORIZATION_ID = "e2e-clinical-001-gemini"
_RESOURCE = "MHS-PAT-001"


def main(argv=None):
    chosen = sys.argv[1:] if argv is None else argv
    if chosen not in ([], ["once"]):
        return 2
    try:
        report = run(sys.stdin, os.environ)
    except ProviderError as error:
        sys.stdout.write(json.dumps(_failure(error.reason)) + "\n")
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
    if not environ.get("FEDERATION_BASE_URL") or not environ.get("FEDERATION_PARTICIPANT_TOKEN"):
        raise ProviderError("federation_unconfigured")
    directory = _directory(environ)
    selected = clock or (lambda: datetime.now(timezone.utc))
    return _execute(directory, credential, environ, selected)


def _require_phrase(stdin):
    interactive = getattr(stdin, "isatty", None)
    if not callable(interactive) or interactive() is not True:
        raise ProviderError("confirmation_required")
    sys.stderr.write(
        "E2E-CLINICAL-001: una solicitud de resumen de laboratorio sintetico.\n"
        "Lee Mini HIS y Mini LIS solo por Clinical Federation. Una llamada Gemini.\n"
        "Sin reintento. El resultado queda pendiente de revision humana.\n"
        "Escriba la frase de confirmacion:\n")
    from app.clinical_lab_summary.consent import PHRASE
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
    directory = Path(root) / "healthcare-ai-interoperability-lab" / "e2e-clinical-001"
    repo = Path(__file__).resolve().parents[4]
    try:
        directory.resolve().relative_to(repo.resolve())
    except ValueError:
        return directory
    raise ProviderError("not_configured")


def _execute(directory, credential, environ, clock):
    from app.clinical_federation_client import ClinicalFederationClient
    from app.clinical_lab_summary.consent import PHRASE, OperationalClinicalConsent
    from app.clinical_lab_summary.graph import LabSummaryGraph
    from app.enterprise_ai_processing.durable_resolver import LedgerDurableAuthorization
    from app.enterprise_ai_processing.sqlite_ledger import SQLiteExecutionLedger
    from app.model_gateway.gateway import NeutralModelGateway
    from app.model_gateway.sdk_bridge import gemini_operational_reservation

    directory.mkdir(parents=True, exist_ok=True)
    issuer = _Issuer(clock)
    admin = issuer.issue("ORG-A", "administrator")
    executor = issuer.issue("ORG-A", "executor")
    ledger = SQLiteExecutionLedger(directory, issuer, clock)
    fresh = not ledger.path.exists()
    try:
        _prepare(ledger, admin, executor.principal_id, clock, fresh)
        _claim_marker(directory)
        reservation = gemini_operational_reservation()
        consent = OperationalClinicalConsent.issue(
            {"GEMINI_API_KEY": credential}, authorization_id=AUTHORIZATION_ID,
            deployment_id="gemini-sdk-a", organization_id="ORG-A",
            principal_id=executor.principal_id, resource_id=_RESOURCE, phrase=PHRASE,
            interactive=True)
        client = ClinicalFederationClient(
            environ["FEDERATION_BASE_URL"], environ["FEDERATION_PARTICIPANT_TOKEN"],
            organization_id="org-mini-his", patient_system_key="mini-his",
            patient_identifier_system="https://lab.local/mini-his/patient",
            sources=("mini-his", "mini-lis"))
        graph = LabSummaryGraph(
            NeutralModelGateway(resolver=LedgerDurableAuthorization(ledger)), client,
            _audit(directory / "mcp-audit.jsonl"), directory / "review.sqlite3")
        state = graph.invoke(executor, AUTHORIZATION_ID, reservation, _RESOURCE, consent)
        report = _report(state, reservation)
        _write_receipt(directory, report)
        return report
    finally:
        ledger.close()


def _prepare(ledger, admin, principal_id, clock, fresh):
    from app.enterprise_ai_processing.execution_types import ExecutionError
    from app.enterprise_ai_processing.remote_authorization import (
        CLINICAL_OPERATION_ID, CLINICAL_POLICY_REF, RemoteAuthorization)
    from app.model_gateway.sdk_bridge import gemini_operational_reservation
    ledger.initialize(admin)
    if fresh:
        ledger.migrate_to_v2(admin)
        ledger.migrate_to_v3(admin)
        ledger.migrate_to_v4(admin)
        ledger.migrate_remote_audit_v2(admin)
        ledger.migrate_to_v5(admin)
        ledger.migrate_to_v6(admin)
    now = clock()
    record = RemoteAuthorization(
        AUTHORIZATION_ID, "ORG-A", "gemini-sdk-a", "gemini", "gemini-3.5-flash-lite",
        now - timedelta(seconds=1), now + timedelta(minutes=10),
        operation_id=CLINICAL_OPERATION_ID, policy_ref=CLINICAL_POLICY_REF,
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
        os.write(handle, b"provider=gemini\nmodel=gemini-3.5-flash-lite\noperation=lab-result-summary-v1\n")
    finally:
        os.close(handle)


def _audit(path):
    def write(event):
        line = json.dumps(event, ensure_ascii=True, sort_keys=True)
        if "AIza" in line or "GEMINI_API_KEY" in line:
            raise OSError("secret")
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    return write


def _report(state, reservation):
    passed = state.get("phase") == "PENDING_REVIEW" and state.get("review_status") == "pending"
    return {
        "result": "PASS" if passed else "FAIL",
        "reason": state.get("reason"),
        "phase": state.get("phase"),
        "provider": "gemini",
        "model": "gemini-3.5-flash-lite",
        "operation_id": "lab-result-summary-v1",
        "review_status": state.get("review_status"),
        "requests_sent": state.get("requests_sent", 0),
        "provider_request_id": state.get("provider_request_id"),
        "response_status": state.get("response_status"),
        "input_tokens": state.get("input_tokens"),
        "output_tokens": state.get("output_tokens"),
        "reserved_microusd": state.get("reserved_microusd", reservation),
        "estimated_microusd": state.get("estimated_microusd"),
        "cost_kind": state.get("cost_kind"),
        "cost_exact": False,
        "provider_charge": "unconfirmed",
        "model_calls": state.get("requests_sent", 0),
    }


def _write_receipt(directory, report):
    text = json.dumps(report, sort_keys=True)
    if "AIza" in text or "GEMINI_API_KEY" in text:
        raise ProviderError("invalid_input")
    (directory / "receipt.json").write_text(text + "\n", encoding="utf-8")


def _failure(reason):
    return {
        "result": "FAIL", "reason": reason, "provider": "gemini",
        "model": "gemini-3.5-flash-lite", "operation_id": "lab-result-summary-v1",
        "requests_sent": 0, "cost_exact": False, "provider_charge": "unconfirmed",
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
