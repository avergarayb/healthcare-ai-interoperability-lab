"""Unit coverage for the operational demonstration. The real run is opt-in."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "end-to-end-demo"))

from demo_profile import (  # noqa: E402
    AI_SERVICE_TOKEN,
    CONTAINER,
    HIS_EXCHANGE_TOKEN,
    HIS_FEDERATION_TOKEN,
    LIS_TOKEN,
    assert_profile_is_isolated,
    check_dependencies,
    fhir_arguments,
    postgres_command,
)
from demo_runner import (  # noqa: E402
    DemoFailure,
    DemoIo,
    _ai_environment,
    new_execution_id,
    public_report,
    refuse_if_running,
    review_page_has_evidence,
    run_negative,
    run_positive,
    stop_recorded,
)


class FakeIo(DemoIo):
    def __init__(self, linked: bool = True, fail: str | None = None) -> None:
        self.linked = linked
        self.fail = fail
        self.workflow_calls: list[str] = []
        self.result_urls: list[str] = []
        super().__init__(
            his="http://his.test",
            lis="http://lis.test",
            fhir="http://fhir.test",
            request=self._request,
            federation=self._federation,
            workflow=self._workflow,
        )

    def _request(self, method, url, token="", body=None):
        self.calls.append(f"{method} {url}")
        if self.fail == "down":
            raise DemoFailure("service_unavailable")
        if url.endswith("/consultations"):
            patient = "MHS-PAT-003" if "MHS-PAT-003" in url else "MHS-PAT-002"
            encounter = "MHS-CON-003" if patient == "MHS-PAT-003" else "MHS-CON-002"
            return 200, [{"consultationId": encounter, "patientId": patient, "status": "completed", "endedAt": "2026-03-01T10:00:00Z"}]
        if url.endswith("/patients/MHS-PAT-003"):
            return 200, {"patientId": "MHS-PAT-003", "familyName": "Hidden", "givenName": "Hidden", "birthDate": "1991-07-19", "administrativeSex": "female"}
        if url.endswith("/api/exchange/v1/orders"):
            return 201, {"correlationId": "EXC-OTHER", "destination": {"orderId": "MLS-OTHER"}}
        if url.endswith("/results"):
            self.result_urls.append(url)
            return 201, {"status": "FINAL"}
        if url.endswith("/lab-orders"):
            order = "MHS-LAB-NEG" if body and "NEG" in body["testDescription"] else "MHS-LAB-POS"
            return 201, {"orderId": order}
        if url.endswith("/submission"):
            if self.fail == "correlation":
                return 200, {"correlationId": "", "destination": {}}
            lis = "MLS-NEG" if "MHS-LAB-NEG" in url else "MLS-POS"
            return 200, {"correlationId": "EXC-" + lis, "destination": {"orderId": lis}}
        raise AssertionError(url)

    def _federation(self, patient_id: str):
        lis = "MLS-NEG" if patient_id == "MHS-PAT-003" else "MLS-POS"
        his = "MHS-LAB-NEG" if patient_id == "MHS-PAT-003" else "MHS-LAB-POS"
        identifier = his if self.linked else "UNRELATED"
        return {
            "status": "complete",
            "requestingOrganizationId": "org-mini-his",
            "entries": [
                {
                    "resource": {
                        "resourceType": "ServiceRequest",
                        "id": lis,
                        "identifier": [{"system": "https://lab.local/mini-lis/order", "value": identifier}],
                    }
                }
            ],
        }

    def _workflow(self, patient_id: str):
        self.workflow_calls.append(patient_id)
        if patient_id == "MHS-PAT-003":
            return {
                "status": "completed",
                "currentStep": "completion",
                "reviewCaseId": None,
                "protocol": {
                    "protocolId": "CROSS_ORG_LAB_RESULT_REVIEW_V1",
                    "evaluationStatus": "not_matched",
                    "reasonCodes": ["result_order_mismatch"],
                },
                "evidence": [],
                "clinicalContext": {},
            }
        evidence = [
            "Encounter/MHS-CON-002",
            "ServiceRequest/MHS-LAB-POS",
            "ServiceRequest/MLS-POS",
            "Observation/MLS-RES-POS",
        ]
        rows = [
            {"protocolReference": evidence[0], "sourceKey": "mini-his", "source": "https://lab.local/mini-his"},
            {"protocolReference": evidence[1], "sourceKey": "mini-his", "source": "https://lab.local/mini-his"},
            {"protocolReference": evidence[2], "sourceKey": "mini-lis", "source": "https://lab.local/mini-lis"},
            {"protocolReference": evidence[3], "sourceKey": "mini-lis", "source": "https://lab.local/mini-lis"},
        ]
        return {
            "status": "waiting_human",
            "currentStep": "await_human",
            "reviewCaseId": "case-positive",
            "protocol": {
                "protocolId": "CROSS_ORG_LAB_RESULT_REVIEW_V1",
                "evaluationStatus": "matched",
                "reasonCodes": ["cross_org_lab_result_requires_review"],
            },
            "evidence": evidence,
            "clinicalContext": {"federation": {"resources": rows[:1] + rows[3:], "reports": rows[1:3]}},
        }


def test_missing_dependencies_are_reported_without_docker():
    assert check_dependencies(which=lambda _name: None) == ["docker", "mvn.cmd", "java"]


def test_profile_does_not_select_hapi_or_reserved_ports():
    assert_profile_is_isolated()
    text = " ".join(fhir_arguments("exchange.sqlite", "http://127.0.0.1:1", "http://127.0.0.1:2"))
    assert "clinical-read.source" not in text
    assert "hapi" not in text.lower()
    assert "--federation.security-audit.store-path=federation-security-audit.sqlite" in text
    command = postgres_command()
    assert command[0] == "docker"
    assert "postgres:16-alpine" in command
    assert CONTAINER in command


def test_profile_isolates_audit_stores_and_component_credentials(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "operator-provider-secret")
    monkeypatch.setenv("SECURITY_AUDIT_DB_PATH", "operator-audit.sqlite3")
    monkeypatch.setenv("JAVA_HOME", str(tmp_path / "operator-jdk"))
    (tmp_path / "review-login.secret").write_text("login-secret-" + "a" * 32, encoding="utf-8")
    (tmp_path / "form-signing.secret").write_text("form-secret-" + "b" * 32, encoding="utf-8")

    from demo_runner import _java_env

    env = _ai_environment(tmp_path)
    java_env = _java_env()
    fhir = " ".join(
        fhir_arguments(
            str(tmp_path / "exchange.sqlite"),
            "http://127.0.0.1:18295",
            "http://127.0.0.1:18296",
        )
    )

    assert env["SECURITY_AUDIT_DB_PATH"] == str(tmp_path / "security-audit.sqlite3")
    assert env["AI_REVIEW_DB_PATH"] == str(tmp_path / "review.sqlite3")
    assert env["HUMAN_SESSION_DB_PATH"] == str(tmp_path / "human-session.sqlite3")
    assert "operator-audit.sqlite3" not in env.values()
    assert "operator-provider-secret" not in env.values()
    assert java_env["JAVA_HOME"] == str(tmp_path / "operator-jdk")
    assert f"--federation.security-audit.store-path={(tmp_path / 'federation-security-audit.sqlite').as_posix()}" in fhir
    assert len({LIS_TOKEN, HIS_EXCHANGE_TOKEN, HIS_FEDERATION_TOKEN, AI_SERVICE_TOKEN}) == 4


def test_unavailable_service_stops_before_the_workflow():
    io = FakeIo(fail="down")
    with pytest.raises(DemoFailure) as caught:
        run_negative(io, "E2E-1")
    assert caught.value.code == "service_unavailable"
    assert io.workflow_calls == []


def test_positive_and_negative_scenarios_use_distinct_orders():
    execution = "E2E-UNIT"
    negative_io = FakeIo()
    positive_io = FakeIo()
    negative = run_negative(negative_io, execution)
    positive = run_positive(positive_io, execution)
    assert negative["evaluationStatus"] == "not_matched"
    assert negative["reviewCaseId"] is None
    assert positive["evaluationStatus"] == "matched"
    assert positive["langGraphStatus"] == "waiting_human"
    assert positive["currentStep"] == "await_human"
    assert positive["reviewCaseId"] == "case-positive"
    assert negative_io.result_urls == ["http://lis.test/orders/MLS-OTHER/results"]
    assert positive_io.result_urls == ["http://lis.test/orders/MLS-POS/results"]
    assert {row["sourceKey"] for row in positive["provenance"]} == {"mini-his", "mini-lis"}


def test_incorrect_correlation_does_not_start_the_workflow():
    io = FakeIo(linked=False)
    with pytest.raises(DemoFailure) as caught:
        run_positive(io, "E2E-BAD")
    assert caught.value.code == "correlation_mismatch"
    assert io.workflow_calls == []


def test_missing_exchange_identifier_does_not_start_the_workflow():
    io = FakeIo(fail="correlation")
    with pytest.raises(DemoFailure) as caught:
        run_positive(io, "E2E-BLANK")
    assert caught.value.code == "correlation_missing"
    assert io.workflow_calls == []


def test_report_hides_tokens_names_and_supports_review_evidence():
    io = FakeIo()
    scenario = run_positive(io, "E2E-REPORT")
    scenario["familyName"] = "Hidden"
    scenario["token"] = LIS_TOKEN
    report = public_report("E2E-REPORT", [scenario], "http://127.0.0.1:18290/review-cases/case-positive")
    rendered = json.dumps(report)
    assert "Hidden" not in rendered
    assert LIS_TOKEN not in rendered
    assert report["hapiRequired"] is False
    assert report["productionClinicalSystem"] is False
    html = (
        "Encounter/MHS-CON-002 origen mini-his "
        "ServiceRequest/MHS-LAB-POS origen mini-his "
        "ServiceRequest/MLS-POS origen mini-lis "
        "Observation/MLS-RES-POS origen mini-lis "
        "El modo federado no usa Clinical Read de una sola fuente como evidencia de esta evaluación."
    )
    assert review_page_has_evidence(html, scenario["evidence"])


def test_reexecution_ids_differ_and_a_live_run_is_refused():
    assert new_execution_id() != new_execution_id()
    with pytest.raises(DemoFailure) as caught:
        refuse_if_running({"running": True})
    assert caught.value.code == "demo_already_running"


def test_cleanup_removes_only_the_demo_container():
    removed = []
    killed = []
    stop_recorded({"pids": [4], "container": CONTAINER}, killed.append, removed.append)
    assert killed == [4]
    assert removed == [CONTAINER]
    with pytest.raises(DemoFailure) as caught:
        stop_recorded({"pids": [9], "container": "hapi-fhir"}, killed.append, removed.append)
    assert caught.value.code == "cleanup_refused"
    assert killed == [4]


def test_failed_start_is_released_even_when_keep_was_requested():
    from demo_runner import release_resources

    assert release_resources(False, True) is True
    assert release_resources(True, True) is False
    assert release_resources(True, False) is True
    assert release_resources(False, False) is True


def test_check_does_not_start_processes(monkeypatch):
    import subprocess

    calls = []
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: calls.append(args))
    from run_demo import main

    assert main(["run_demo.py", "check"]) == 0
    assert calls == []


def test_inherited_credentials_are_dropped_and_secret_files_are_restricted(tmp_path, monkeypatch):
    import os
    import subprocess

    monkeypatch.setenv("GEMINI_API_KEY", "habitual-key")
    monkeypatch.setenv("MODEL_BOUNDARY_SERVICE_TOKEN", "habitual-token")
    from demo_runner import _his_arguments, _scrubbed_environment, _write_secrets

    env = _scrubbed_environment()
    assert "GEMINI_API_KEY" not in env
    assert "MODEL_BOUNDARY_SERVICE_TOKEN" not in env
    assert "PATH" in env
    _write_secrets(tmp_path)
    secret = (tmp_path / "review-login.secret").read_text(encoding="utf-8")
    rendered = json.dumps(public_report("E2E-SECRET", [], "http://127.0.0.1:18290/review-cases/case"))
    assert secret not in rendered
    assert "habitual-key" not in rendered
    arguments = " ".join(_his_arguments(tmp_path))
    assert (tmp_path / "mini-his.sqlite").as_posix() in arguments
    assert "data/mini-his.sqlite" not in arguments
    if os.name == "nt":
        listed = subprocess.run(["icacls", str(tmp_path / "review-login.secret")], capture_output=True, text=True)
        assert listed.returncode == 0
        assert "Everyone" not in listed.stdout
        assert "Todos" not in listed.stdout
        assert "BUILTIN\\Users" not in listed.stdout
        assert "Usuarios" not in listed.stdout


def test_single_mode_and_existing_protocols_stay_in_place(monkeypatch):
    monkeypatch.delenv("AI_CLINICAL_CONTEXT_MODE", raising=False)
    from app.config import Settings
    from app.langgraph_workflow_orchestration import PROTOCOL_IDS

    assert Settings.from_env().clinical_context_mode == "single"
    assert PROTOCOL_IDS["post_consultation"] == "POST_CONSULTATION_RESULT_REVIEW_V1"
    assert PROTOCOL_IDS["missed_follow_up"] == "MISSED_FOLLOW_UP_REVIEW_V1"
    assert PROTOCOL_IDS["cross_org_lab_result"] == "CROSS_ORG_LAB_RESULT_REVIEW_V1"
