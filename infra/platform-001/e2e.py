"""HTTP demonstration for one jurisdiction profile.

The durable ledger is Windows-only, so this runner executes on the host and
calls the published federation port. MCP and LangGraph stay in process. The
model client is intercepted. Container-to-container HTTP and the blocked
provider socket are probe.py.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit


def _entries_contain(envelope: dict, marker: str) -> bool:
    return marker in json.dumps(envelope.get("entries", []))


_STAGE = {"value": "start"}


def _mark(name: str) -> None:
    _STAGE["value"] = name


def run() -> dict:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from profiles import ISSUER, binding, require_profile

    profile_id = require_profile(os.environ.get("PLATFORM_PROFILE", ""))
    from profiles import PROFILES
    selected = PROFILES[profile_id]
    federation_url = os.environ.get("PLATFORM_FEDERATION_URL", "").strip().rstrip("/")
    if os.environ.get("GEMINI_API_KEY", "").strip():
        raise SystemExit("provider_key_present")
    if os.name != "nt":
        raise SystemExit("ledger_windows_only")
    parts = urlsplit(federation_url)
    if parts.hostname != "127.0.0.1" or parts.port != selected["published_port"]:
        raise SystemExit("profile_rejected")

    from app.clinical_federation_client import ClinicalFederationClient, FederationClientError
    from app.clinical_lab_summary.review import (
        IamReviewer, ReviewError, decide, iam_principal_id, read_review,
    )
    from app.jurisdiction_lab.profile import PERU, SPAIN
    from app.longitudinal_lab.compare import compare_envelope
    from app.longitudinal_lab.graph import LongitudinalLabGraph
    from app.longitudinal_lab.series import series_for
    from tests.test_lab_summary import _gemini
    from tests.test_longitudinal_lab import _laboratory, _permit, _summary
    from tests.test_model_gateway_egress_gemini import _body

    profile = PERU if profile_id == PERU.profile_id else SPAIN
    if profile.profile_id != profile_id:
        raise SystemExit("profile_rejected")
    token = os.environ.get("AI_FEDERATION_PARTICIPANT_TOKEN", "").strip()
    token_file = os.environ.get("PLATFORM_TOKEN_FILE", "").strip()
    if not token and token_file:
        token = Path(token_file).read_text(encoding="utf-8").strip()
    if not token:
        raise SystemExit("federation_unconfigured")

    import httpx
    http = httpx.Client(timeout=20.0, follow_redirects=False)
    try:
        federation = ClinicalFederationClient(
            federation_url, token, organization_id="org-mini-his",
            patient_system_key="mini-his", patient_identifier_system=profile.patient_system,
            sources=(profile.source_key,), http_client=http)
        _mark("federation")
        envelope = federation.query(profile.patient_value)
        if envelope.get("status") != "complete" or not envelope.get("entries"):
            raise SystemExit("federation_incomplete")
        try:
            other = federation.query(selected["other_patient"])
        except FederationClientError as error:
            other_outcome = error.code
        else:
            if _entries_contain(other, selected["other_patient"]):
                raise SystemExit("jurisdiction_leak")
            other_outcome = "isolated"
        _mark("compare")
        chart, evidence = compare_envelope(envelope, profile)
        if chart["unit"] not in {"g/dL", "mg/dL"} or evidence["ucum_system"] != "http://unitsofmeasure.org":
            raise SystemExit("ucum_rejected")
        if evidence["organization_id"] != profile.organization_id:
            raise SystemExit("organization_rejected")

        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        if not os.environ.get("PLATFORM_LEDGER_ROOT") or not os.environ.get("PLATFORM_REVIEW_DB"):
            raise SystemExit("ledger_unconfigured")
        ledger_root = Path(os.environ["PLATFORM_LEDGER_ROOT"]).resolve()
        ledger_root.mkdir(parents=True, exist_ok=True)
        ledger_dir = ledger_root / stamp
        review_path = Path(os.environ["PLATFORM_REVIEW_DB"]).resolve()
        review_path.parent.mkdir(parents=True, exist_ok=True)
        _mark("ledger")
        lab = _laboratory(ledger_dir, profile)
        ledger_path = Path(lab.ledger.path)
        try:
            _permit(lab, profile)
            payload = _summary(chart, profile)
            gemini, sends = _gemini(
                lambda request: httpx.Response(200, json=_body(payload), request=request))
            from app.longitudinal_lab.consent import PHRASE, OperationalLongitudinalConsent
            from tests.test_model_gateway_durable_authorization import _gateway
            consent = OperationalLongitudinalConsent.issue(
                {"GEMINI_API_KEY": "platform-intercepted-marker"}, profile=profile,
                principal_id=lab.executor[profile.organization_id].principal_id,
                phrase=PHRASE, interactive=True, http_client=gemini)
            graph = LongitudinalLabGraph(
                _gateway(lab), federation, lambda _event: None, review_path, profile)
            _mark("graph")
            state = graph.invoke(
                lab.executor[profile.organization_id], series_for(profile).authorization_id, 1000,
                profile.patient_value, consent)
        finally:
            lab.close()
        if state.get("phase") != "PENDING_REVIEW":
            raise SystemExit(state.get("reason") or "review_not_pending")
        if len(sends) != 1 or sends[0].url.host != "generativelanguage.googleapis.com":
            raise SystemExit("model_transport_rejected")
        if any(item.url.host == "api.openai.com" for item in sends):
            raise SystemExit("provider_reachable")

        review_id = state["review_id"]
        stored = read_review(review_path, review_id)
        rows = stored["longitudinal_evidence"]
        if len(rows) != 1 or rows[0]["ucum_code"] != chart["unit"]:
            raise SystemExit("evidence_rejected")
        if rows[0]["organization_id"] != profile.organization_id:
            raise SystemExit("organization_rejected")

        ai_url = os.environ.get("PLATFORM_AI_URL", "").rstrip("/")
        if not ai_url.startswith("http://127.0.0.1:"):
            raise SystemExit("profile_rejected")
        anonymous = http.get(f"{ai_url}/lab-summaries/{review_id}")
        if anonymous.status_code != 303 or "/lab-review-iam/login" not in anonymous.headers.get("location", ""):
            raise SystemExit("iam_bypass")
        if profile.patient_value in anonymous.text:
            raise SystemExit("unauthenticated_disclosure")
        denied = http.post(
            f"{ai_url}/lab-summaries/{review_id}/decision",
            content=b"decision=approved&note=sintetica",
            headers={"Content-Type": "application/x-www-form-urlencoded"})
        if denied.status_code != 303:
            raise SystemExit("iam_bypass")
        discovery = http.get(ISSUER + "/.well-known/openid-configuration")
        document = discovery.json()
        if discovery.status_code != 200 or document.get("issuer") != ISSUER:
            raise SystemExit("discovery_rejected")
        if not str(document.get("jwks_uri", "")).startswith(ISSUER + "/"):
            raise SystemExit("discovery_rejected")

        reviewer = binding("reviewer-pe" if profile_id.startswith("pe-") else "reviewer-es")
        other = binding("reviewer-other")
        auditor = binding("auditor-pe")
        try:
            IamReviewer(
                iam_principal_id(ISSUER, auditor["sub"]), ISSUER, auditor["sub"],
                auditor["organization_id"], auditor["role"], "session-auditor")
        except ReviewError as error:
            auditor_outcome = error.reason
        else:
            raise SystemExit("auditor_permitted")
        if auditor_outcome != "role_denied":
            raise SystemExit("auditor_permitted")
        foreign = IamReviewer(
            iam_principal_id(ISSUER, other["sub"]), ISSUER, other["sub"],
            other["organization_id"], other["role"], "session-other")
        try:
            decide(review_path, review_id, foreign, "rejected", "sintetica", "2026-11-17T20:00:00.000000Z")
        except ReviewError as error:
            foreign_outcome = error.reason
        else:
            raise SystemExit("organization_permitted")
        if foreign_outcome != "organization_denied":
            raise SystemExit("organization_permitted")
        owner = IamReviewer(
            iam_principal_id(ISSUER, reviewer["sub"]), ISSUER, reviewer["sub"],
            reviewer["organization_id"], reviewer["role"], "session-reviewer")
        decide(review_path, review_id, owner, "approved", "sintetica", "2026-11-17T20:05:00.000000Z")
        try:
            decide(review_path, review_id, owner, "rejected", "sintetica", "2026-11-17T20:06:00.000000Z")
        except ReviewError as error:
            second = error.reason
        else:
            raise SystemExit("second_decision_accepted")
        if second != "already_decided":
            raise SystemExit("second_decision_accepted")
        final = read_review(review_path, review_id)
        if final["status"] != "pending" or final["decision"]["decision"] != "approved":
            raise SystemExit("audit_rejected")
        if not final["decision"].get("reviewer_id"):
            raise SystemExit("audit_rejected")

        from sqlite_backup import copy_sqlite, schema_version
        copied = copy_sqlite(ledger_path, ledger_root / "backup" / stamp)
        version = schema_version(copied)
        if version != 9:
            raise SystemExit("schema_rejected")
        report = {
            "outcome": "passed",
            "profile": profile_id,
            "organization": profile.organization_id,
            "patient": profile.patient_value,
            "correlation": envelope.get("correlationId"),
            "federation_status": envelope.get("status"),
            "other_patient": other_outcome,
            "phase": state["phase"],
            "review_id": review_id,
            "code": rows[0]["code"],
            "ucum": rows[0]["ucum_code"],
            "difference": rows[0]["absolute_difference"],
            "direction": rows[0]["direction"],
            "model_calls": len(sends),
            "model_host": sends[0].url.host,
            "provider_socket": "intercepted_on_host",
            "unauthenticated_status": anonymous.status_code,
            "discovery_issuer": document.get("issuer"),
            "auditor": auditor_outcome,
            "other_organization": foreign_outcome,
            "decision": final["decision"]["decision"],
            "second_decision": second,
            "summary_status": final["status"],
            "schema_version": version,
            "backup": copied.name,
        }
        (ledger_root / "platform-last.json").write_text(
            json.dumps(report, ensure_ascii=True), encoding="utf-8")
        return report
    finally:
        http.close()


def main() -> None:
    try:
        report = run()
    except SystemExit as error:
        reason = error.code if isinstance(error.code, str) else "failed"
        print(json.dumps({"outcome": "failed", "reason": reason}))
        raise SystemExit(1)
    except Exception as error:
        reason = getattr(error, "reason", None) or getattr(error, "code", None) or type(error).__name__
        print(json.dumps({"outcome": "failed", "reason": str(reason), "stage": _STAGE["value"]}))
        raise SystemExit(1)
    print(json.dumps(report))


if __name__ == "__main__":
    main()
