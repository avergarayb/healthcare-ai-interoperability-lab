"""One hospital lab summary for the showcase portal.

The graph, the MCP tool, the federation client, the durable permit and the
human decision are the ones the hospital runner already uses. This module
does not open a provider socket and does not accept an organization from
the browser.
"""
import json
import os
import re
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import httpx

from app.clinical_federation_client import ClinicalFederationClient, FederationClientError
from app.clinical_lab_summary.consent import PHRASE, OperationalClinicalConsent
from app.clinical_lab_summary.graph import LabSummaryGraph
from app.clinical_lab_summary.mcp_tool import TOOL_NAME
from app.clinical_lab_summary.policy import DEPLOYMENT_ID, PATIENT_ID
from app.clinical_lab_summary.review import (
    ReviewError,
    Reviewer,
    decide,
    list_reviews,
    prepare_decision_store,
    read_review,
)
from app.enterprise_ai_processing.durable_resolver import LedgerDurableAuthorization
from app.enterprise_ai_processing.execution_types import ExecutionError
from app.enterprise_ai_processing.remote_authorization import (
    CLINICAL_OPERATION_ID,
    CLINICAL_POLICY_REF,
    RemoteAuthorization,
)
from app.enterprise_ai_processing.sqlite_ledger import SQLiteExecutionLedger
from app.enterprise_llm_providers.errors import ProviderError
from app.enterprise_llm_providers.gemini_configuration import ALLOWED_MODEL
from app.human_session import DEVELOPMENT_AUTHENTICATOR_V1
from app.model_gateway.gateway import NeutralModelGateway


PATIENT = PATIENT_ID
ORGANIZATION = "org-mini-his"
REVIEWER_ID = "hl7-reviewer"
SESSION_ID = "showcase-lab-summary"
BUDGET = 1000
_CASE = re.compile(r"sum-[0-9a-f]{12}\Z")
_ACTOR = re.compile(r"[a-z0-9-]{1,32}\Z")
_LOCK = threading.Lock()
_OPEN = {}


class SummaryRejected(Exception):
    def __init__(self, reason, status=409):
        self.reason = reason
        self.status = status
        super().__init__(reason)


def summary_root():
    configured = os.environ.get("SHOWCASE_SUMMARY_ROOT", "").strip()
    if configured:
        path = Path(configured)
    else:
        base = os.environ.get("TEMP") or os.environ.get("TMP") or "/tmp"
        path = Path(base) / "showcase-accept" / "lab-summary"
    if not path.is_absolute():
        raise SummaryRejected("summary_unconfigured", 503)
    return path


def federation_client(settings):
    token = settings.federation_participant_token
    base = settings.model_boundary_base_url
    loopback = base.startswith("http://127.0.0.1:") or base.startswith("http://localhost:")
    if not token or not loopback:
        raise FederationClientError("federation_unconfigured")
    return ClinicalFederationClient(
        base, token, organization_id=ORGANIZATION, patient_system_key="mini-his",
        patient_identifier_system="https://lab.local/mini-his/patient",
        sources=("mini-his", "mini-lis"), timeout_seconds=20)


def prepare_case(root, federation, actor_id):
    if _ACTOR.fullmatch(actor_id or "") is None:
        raise SummaryRejected("invalid_input", 400)
    with _LOCK:
        authorization_id = "sum-" + uuid4().hex[:12]
        lab = _lab(root, authorization_id)
        _permit(lab, authorization_id)
        view = _invoke(lab, federation, authorization_id, actor_id)
        _remember(root, view)
        return view


def replay_case(root, authorization_id, federation):
    _require_case(authorization_id)
    with _LOCK:
        if not _known(root, authorization_id):
            raise SummaryRejected("not_found", 404)
        lab = _lab(root, authorization_id)
        state, _events, _chart = _graph_once(lab, federation, authorization_id)
        if state.get("phase") == "PENDING_REVIEW":
            raise SummaryRejected("replay_denied", 409)
        raise SummaryRejected(state.get("reason") or "replay_denied", 409)


def decide_case(root, authorization_id, decision):
    _require_case(authorization_id)
    if decision not in {"approved", "rejected"}:
        raise SummaryRejected("invalid_decision", 400)
    with _LOCK:
        if not _known(root, authorization_id):
            raise SummaryRejected("not_found", 404)
        review_path = _review(root)
        review_id = _review_id(review_path, authorization_id)
        prepare_decision_store(review_path)
        reviewer = Reviewer(REVIEWER_ID, DEVELOPMENT_AUTHENTICATOR_V1, SESSION_ID)
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        try:
            decide(
                review_path, review_id, reviewer, decision,
                "Operador de planta org-mini-his. Sesion local de desarrollo, no OIDC.", stamp)
        except ReviewError as error:
            status = 409 if error.reason == "already_decided" else 400
            raise SummaryRejected(error.reason, status) from None
        view = _load(root, authorization_id)
        view["decision"] = _decision(read_review(review_path, review_id))
        view["audit"] = _audit_lines(read_review(review_path, review_id))
        view["reviewStatus"] = "decided"
        _write(root, view)
        return view


def read_case(root, authorization_id):
    _require_case(authorization_id)
    with _LOCK:
        if not _known(root, authorization_id):
            raise SummaryRejected("not_found", 404)
        view = _load(root, authorization_id)
        try:
            report = read_review(_review(root), view["reviewId"])
        except (ReviewError, KeyError):
            return view
        view["decision"] = _decision(report)
        view["audit"] = _audit_lines(report)
        if view["decision"] is not None:
            view["reviewStatus"] = "decided"
        return view


def latest_case(root):
    with _LOCK:
        index = _index(root)
        if not index.exists():
            return {"caseId": None}
        ids = [line.strip() for line in index.read_text(encoding="utf-8").splitlines() if line.strip()]
        if not ids:
            return {"caseId": None}
        return _load_latest(root, ids[-1])


def _load_latest(root, authorization_id):
    if not _known(root, authorization_id):
        return {"caseId": None}
    view = _load(root, authorization_id)
    try:
        report = read_review(_review(root), view["reviewId"])
    except (ReviewError, KeyError):
        return view
    view["decision"] = _decision(report)
    view["audit"] = _audit_lines(report)
    if view["decision"] is not None:
        view["reviewStatus"] = "decided"
    return view


def _invoke(lab, federation, authorization_id, actor_id):
    state, events, chart = _graph_once(lab, federation, authorization_id)
    if state.get("phase") != "PENDING_REVIEW":
        raise SummaryRejected(state.get("reason") or "summary_rejected", 409)
    review_id = _review_id(lab.review, authorization_id)
    report = read_review(lab.review, review_id)
    current, historical, reports = _split(chart.get("facts") or [])
    tool = TOOL_NAME if any(item.get("tool") == TOOL_NAME for item in events) else ""
    return {
        "caseId": authorization_id,
        "patientId": PATIENT,
        "organizationId": ORGANIZATION,
        "operator": actor_id,
        "phase": state.get("phase"),
        "reason": state.get("reason"),
        "reviewStatus": "pending",
        "reviewId": review_id,
        "modelMode": "intercepted",
        "operation": CLINICAL_OPERATION_ID,
        "tool": tool,
        "graph": "lab_summary_review",
        "correlationId": getattr(federation, "last_correlation_id", "") or "",
        "current": current,
        "historical": historical,
        "reports": reports,
        "statements": [
            {"text": item.get("text", ""), "sources": [
                {"source": source.get("source"), "kind": source.get("resourceType"), "id": source.get("id")}
                for source in item.get("sources") or []
            ]}
            for item in report["summary"].get("statements") or []
        ],
        "decision": None,
        "reviewer": REVIEWER_ID,
        "authenticator": DEVELOPMENT_AUTHENTICATOR_V1,
        "audit": _audit_lines(report),
    }


def _graph_once(lab, federation, authorization_id):
    events = []
    captured = {}
    client = _intercepted(captured)

    def audit(event):
        if isinstance(event, dict):
            events.append({
                "tool": event.get("tool"),
                "outcome": event.get("outcome"),
                "reason": event.get("reason"),
            })

    access = _executor(lab)
    consent = OperationalClinicalConsent.issue(
        {"GEMINI_API_KEY": "showcase-intercepted"}, authorization_id=authorization_id,
        deployment_id=DEPLOYMENT_ID, organization_id="ORG-A", principal_id=access.principal_id,
        resource_id=PATIENT, phrase=PHRASE, interactive=True, http_client=client)
    graph = LabSummaryGraph(
        NeutralModelGateway(resolver=LedgerDurableAuthorization(lab.ledger)),
        federation, audit, lab.review)
    try:
        state = graph.invoke(access, authorization_id, BUDGET, PATIENT, consent)
    except (ProviderError, FederationClientError) as error:
        reason = getattr(error, "reason", None) or getattr(error, "code", None) or "summary_rejected"
        raise SummaryRejected(reason, 409) from None
    finally:
        client.close()
    return state, events, captured.get("chart") or {"facts": []}


def _intercepted(captured):
    def handler(request):
        chart = _chart(request.content.decode("utf-8"))
        captured["chart"] = chart
        current, historical, reports = _groups(chart.get("facts") or [])
        statements = [_statement(fact, "Resultado vigente.") for fact in current]
        for start in range(0, len(historical), 4):
            statements.append(_historical(historical[start:start + 4]))
        statements.extend(_statement(fact, "Informe consultado.") for fact in reports)
        body = json.dumps({
            "kind": CLINICAL_OPERATION_ID,
            "review": "pending_human_review",
            "statements": statements,
        })
        return httpx.Response(200, json={
            "responseId": "resp_showcase_intercepted",
            "modelVersion": ALLOWED_MODEL,
            "candidates": [{
                "content": {"role": "model", "parts": [{"text": body}]},
                "finishReason": "STOP",
            }],
            "usageMetadata": {
                "promptTokenCount": 40,
                "candidatesTokenCount": 16,
                "thoughtsTokenCount": 0,
            },
        }, request=request)

    return httpx.Client(transport=httpx.MockTransport(handler))


def _statement(fact, prefix):
    unit = fact.get("unit") or ""
    return {
        "text": (prefix + " " + fact["code"] + " " + fact["value"] + " " + unit).strip(),
        "sources": [{"source": fact["source"], "resourceType": fact["resourceType"], "id": fact["id"]}],
    }


def _historical(facts):
    body = "; ".join(
        fact["id"] + " " + fact["code"] + " " + fact["value"] + " " + (fact.get("unit") or "")
        for fact in facts)
    return {
        "text": "Observacion historica, distinta del caso. " + body,
        "sources": [
            {"source": fact["source"], "resourceType": fact["resourceType"], "id": fact["id"]}
            for fact in facts
        ],
    }


def _groups(facts):
    observations = [fact for fact in facts if fact.get("resourceType") == "Observation"]
    latest = {}
    for fact in observations:
        latest[fact.get("source")] = fact.get("id")
    current_ids = set(latest.values())
    current = [fact for fact in observations if fact.get("id") in current_ids]
    historical = [fact for fact in observations if fact.get("id") not in current_ids]
    reports = [fact for fact in facts if fact.get("resourceType") != "Observation"]
    return current, historical, reports


def _split(facts):
    current, historical, reports = _groups(facts)
    return [_public(fact) for fact in current], [_public(fact) for fact in historical], [_public(fact) for fact in reports]


def _public(fact):
    return {
        "source": fact.get("source"),
        "kind": fact.get("resourceType"),
        "id": fact.get("id"),
        "code": fact.get("code"),
        "value": fact.get("value"),
        "unit": fact.get("unit") or "",
    }


def _chart(raw):
    decoded = raw.replace('\\"', '"')
    marker = '{"operation_id":"' + CLINICAL_OPERATION_ID + '"'
    start = decoded.find(marker)
    if start < 0:
        raise SummaryRejected("chart_missing", 409)
    chart, _end = json.JSONDecoder().raw_decode(decoded[start:])
    if chart.get("patient_id") != PATIENT or not isinstance(chart.get("facts"), list):
        raise SummaryRejected("chart_rejected", 409)
    return chart


def _decision(report):
    decision = report.get("decision")
    if not isinstance(decision, dict):
        return None
    return {
        "decision": decision.get("decision"),
        "reviewer": decision.get("reviewer_id"),
        "authenticator": decision.get("reviewer_authenticator"),
        "note": decision.get("note"),
        "decidedAt": decision.get("decided_at"),
    }


def _audit_lines(report):
    lines = []
    for item in report.get("audit") or []:
        lines.append({"event": item.get("event"), "outcome": item.get("outcome"), "actor": ""})
    for item in report.get("decision_audit") or []:
        lines.append({
            "event": item.get("event"),
            "outcome": item.get("outcome"),
            "actor": item.get("actor_id"),
            "decision": item.get("decision"),
        })
    return lines


def _review_id(path, authorization_id):
    for item in list_reviews(path):
        if item.get("authorization_id") == authorization_id:
            return item["review_id"]
    raise SummaryRejected("not_found", 404)


def _review(root):
    return Path(root) / "review.sqlite3"


def _lab(root, case_id):
    path = Path(root) / "ledgers" / case_id
    key = str(path.resolve())
    holder = _OPEN.get(key)
    if holder is not None:
        return holder
    path.mkdir(parents=True, exist_ok=True)
    from tests.enterprise_ai_processing_execution_fixture import TestAccessAuthority

    def clock():
        return datetime.now(timezone.utc)

    issuer = TestAccessAuthority(clock)
    ledger = SQLiteExecutionLedger(path, issuer, clock)
    holder = _Holder(issuer, clock, ledger, _review(root))
    try:
        ledger.initialize(holder.admin)
        for migrate in (
            ledger.migrate_to_v2, ledger.migrate_to_v3, ledger.migrate_to_v4,
            ledger.migrate_remote_audit_v2, ledger.migrate_to_v5, ledger.migrate_to_v6,
        ):
            try:
                migrate(holder.admin)
            except ExecutionError as error:
                if error.reason != "revision_conflict":
                    raise
    except BaseException:
        ledger.close()
        raise
    _OPEN[key] = holder
    return holder


class _Holder:
    def __init__(self, issuer, clock, ledger, review):
        self.issuer = issuer
        self.clock = clock
        self.ledger = ledger
        self.admin = issuer.issue("ORG-A", "administrator")
        self.executor = issuer.issue("ORG-A", "executor")
        self.review = review


def _executor(lab):
    if lab.executor.expires_at <= lab.clock() + timedelta(seconds=30):
        lab.executor = lab.issuer.issue("ORG-A", "executor")
    return lab.executor


def _admin(lab):
    if lab.admin.expires_at <= lab.clock() + timedelta(seconds=30):
        lab.admin = lab.issuer.issue("ORG-A", "administrator")
    return lab.admin


def _permit(lab, authorization_id):
    now = lab.clock()
    record = RemoteAuthorization(
        authorization_id=authorization_id, organization_id="ORG-A", deployment_id=DEPLOYMENT_ID,
        provider_id="gemini", model_id=ALLOWED_MODEL, valid_from=now - timedelta(minutes=1),
        expires_at=now + timedelta(minutes=30), operation_id=CLINICAL_OPERATION_ID,
        policy_ref=CLINICAL_POLICY_REF, principal_id="synthetic-executor", resource_id=PATIENT,
        budget_ceiling_microusd=BUDGET)
    lab.ledger.register_remote_authorization(_admin(lab), record)


def _remember(root, view):
    _write(root, view)
    with _index(root).open("a", encoding="utf-8") as handle:
        handle.write(view["caseId"] + "\n")


def _write(root, view):
    folder = Path(root) / "views"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / (view["caseId"] + ".json")
    target.write_text(json.dumps(view, ensure_ascii=True), encoding="utf-8")


def _load(root, authorization_id):
    target = Path(root) / "views" / (authorization_id + ".json")
    if not target.is_file():
        raise SummaryRejected("not_found", 404)
    return json.loads(target.read_text(encoding="utf-8"))


def _known(root, authorization_id):
    return (Path(root) / "views" / (authorization_id + ".json")).is_file()


def _index(root):
    return Path(root) / "cases.txt"


def _require_case(authorization_id):
    if _CASE.fullmatch(authorization_id or "") is None:
        raise SummaryRejected("not_found", 404)
