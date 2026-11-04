"""Offline TASK 006 harness guards; no providers, product children or Docker."""
from datetime import datetime, timezone
import json
from types import SimpleNamespace

import pytest

import lab
import verify_cross_service_identity as runner


def context(service, expiry=200):
    python = service == "python"
    return dict(context_version="identity-principal-context-v1", principal_type="workload",
                internal_principal_id="fixture-ai-workload" if python else "fixture-python-to-java",
                organization_id="org-lab-a" if python else "org-lab-b",
                audience=runner.AUDIENCES[service], effective_permissions=[runner.PERMISSIONS[service]],
                authentication_method="oauth2_client_credentials", correlation_id="synthetic-correlation",
                authenticated_at=datetime.fromtimestamp(50, timezone.utc).isoformat(),
                expires_at=datetime.fromtimestamp(expiry, timezone.utc).isoformat())


@pytest.mark.parametrize("service", ["python", "java"])
def test_projection_is_minimal_and_token_bounded(monkeypatch, service):
    monkeypatch.setattr(runner.time, "time", lambda: 100)
    runner.projection(context(service), service, SimpleNamespace(expires=200), "synthetic-correlation")


@pytest.mark.parametrize("fault", ["external_subject", "external_issuer", "provider_id", "token", "secret",
                                  "permissions", "organization", "principal", "expiry", "method", "audience", "missing"])
def test_projection_rejects_disclosure_or_changed_authority(monkeypatch, fault):
    monkeypatch.setattr(runner.time, "time", lambda: 100)
    data = context("python")
    if fault in {"external_subject", "external_issuer", "provider_id", "token", "secret"}:
        data[fault] = "synthetic-not-allowed"
    elif fault == "missing":
        del data["correlation_id"]
    else:
        field, value = {"permissions": ("effective_permissions", [runner.PERMISSIONS["java"]]),
                        "organization": ("organization_id", "org-lab-b"),
                        "principal": ("principal_type", "human"),
                        "expiry": ("expires_at", context("python", 201)["expires_at"]),
                        "method": ("authentication_method", "legacy"),
                        "audience": ("audience", runner.AUDIENCES["java"])}[fault]
        data[field] = value
    with pytest.raises(lab.Denied):
        runner.projection(data, "python", SimpleNamespace(expires=200), "synthetic-correlation")


def test_token_is_redacted_and_expiry_is_inconclusive(monkeypatch):
    token = runner.Token("synthetic-secret-token", "audience", "client", 100, 1)
    assert "synthetic-secret-token" not in repr(token)
    monkeypatch.setattr(runner.time, "time", lambda: 100)
    with pytest.raises(runner.Inconclusive):
        token.current()


def matrix(tmp_path, claims=None):
    claims = claims or dict(iat=100, exp=130, aud=runner.AUDIENCES["python"], typ="Bearer", azp="client")
    http = SimpleNamespace(request=lambda *args: {"access_token": "synthetic-not-persisted", "token_type": "Bearer"})
    trust = SimpleNamespace(issuer="http://localhost:18090/realms/healthcare-iam-lab", decode=lambda *args, **kwargs: claims)
    return runner.Matrix(tmp_path, trust, http, {"client": "synthetic-secret"}, [])


@pytest.mark.parametrize("fault", ["long-life", "extra-audience", "purpose", "client"])
def test_issuance_does_not_relax_fixture_profile(tmp_path, fault):
    claims = dict(iat=100, exp=130, aud=runner.AUDIENCES["python"], typ="Bearer", azp="client")
    if fault == "long-life": claims["exp"] = 136
    if fault == "extra-audience": claims["aud"] = [runner.AUDIENCES["python"], runner.AUDIENCES["java"]]
    if fault == "purpose": claims["typ"] = "ID"
    if fault == "client": claims["azp"] = "other"
    with pytest.raises(lab.Denied):
        matrix(tmp_path, claims).issue("client", runner.AUDIENCES["python"])


def test_issuance_evidence_contains_no_token_or_client_secret(tmp_path):
    value = matrix(tmp_path)
    token = value.issue("client", runner.AUDIENCES["python"])
    evidence = json.dumps(value.issuances)
    assert token.encoded not in evidence and value.clients["client"] not in evidence
    assert value.issuances[0]["grant"] == "client_credentials"


def test_expiry_after_response_is_not_counted_as_audience_denial(tmp_path, monkeypatch):
    value = matrix(tmp_path)
    class Response:
        status = 401
        def read(self, _): return b'{"error":"unauthorized"}'
        def __enter__(self): return self
        def __exit__(self, *_): pass
    value.opener = SimpleNamespace(open=lambda *args, **kwargs: Response())
    times = iter([100, 131])
    monkeypatch.setattr(runner.time, "time", lambda: next(times))
    token = runner.Token("synthetic-secret-token", runner.AUDIENCES["python"], "client", 130, 1)
    with pytest.raises(runner.Inconclusive):
        value.check("java", "cross_audience", 401, token)
    assert value.results[0]["status"] == "INCONCLUSIVE"
    assert "synthetic-secret-token" not in json.dumps(value.results)


def test_dead_child_prevents_requests(tmp_path):
    value = matrix(tmp_path)
    value.children = [(SimpleNamespace(poll=lambda: 1), None)]
    with pytest.raises(lab.Denied, match="owned_child_not_running"):
        value.check("python", "missing", 401)


def test_unapproved_clinical_route_is_refused(tmp_path):
    with pytest.raises(lab.Denied, match="unapproved_test_route"):
        matrix(tmp_path).check("java", "not_allowed", 401, legacy=("GET", "/fhir/Patient"))


def test_whole_sequence_retries_with_new_issuances_and_same_token_revocation(tmp_path, monkeypatch):
    value = matrix(tmp_path)
    monkeypatch.setattr(value, "mutate", lambda *args: None)
    issued, observed = [], []
    def issue(client, audience):
        token = runner.Token("synthetic", audience, client, 200, len(issued) + 1)
        issued.append(token)
        return token
    monkeypatch.setattr(value, "issue", issue)
    failed = []
    def check(service, name, expected, token=None, **kwargs):
        if name == "same_AI_cross_audience" and not failed:
            failed.append(True)
            raise runner.Inconclusive()
        value.results.append({"case": name, "status": "PASS"})
        observed.append((name, None if token is None else token.issuance))
    monkeypatch.setattr(value, "check", check)
    monkeypatch.setattr(runner.time, "time", lambda: 200)
    monkeypatch.setattr(runner.time, "sleep", lambda _: None)
    value.execute()
    assert len(issued) == 6
    assert value.results[0]["status"] == "INCONCLUSIVE"
    controls = dict(observed)
    assert controls["AI_own_audience"] == controls["same_AI_cross_audience"] == 4
    assert controls["before_revocation_same_token"] == controls["revoked_same_valid_token"] == controls["explicit_restore_same_valid_token"] == 4


def test_cleanup_attempts_every_owned_child_and_IAM_after_one_stop_fails(tmp_path, monkeypatch):
    stopped, lifecycle, reports = [], [], []
    process1, process2 = SimpleNamespace(poll=lambda: None), SimpleNamespace(poll=lambda: 0)
    def stop(process, log):
        stopped.append(process)
        if process is process2: raise OSError("synthetic")
    monkeypatch.setattr(runner.java, "stop", stop)
    monkeypatch.setattr(lab, "cleanup", lambda *args: lifecycle.append(True))
    monkeypatch.setattr(lab, "inventory", lambda: {"container": ["foreign"], "volume": [], "network": []})
    monkeypatch.setattr(lab, "save", lambda path, data: reports.append(data))
    class Probe:
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def settimeout(self, _): pass
        def connect_ex(self, _): return 1
    monkeypatch.setattr(runner.socket, "socket", lambda: Probe())
    state = dict(port=18090, baseline={"container": ["foreign"], "volume": [], "network": []},
                 owned={"container": ["owned"], "volume": [], "network": []})
    with pytest.raises(lab.Denied, match="cross_service_cleanup_incomplete"):
        runner.cleanup(tmp_path, state, [(process1, None), (process2, None)])
    assert len(stopped) == 2 and lifecycle
    assert reports[0]["baseline_exactly_preserved"] is True
    assert reports[0]["recorded_children_exited"] is False


def test_run_cleans_up_when_a_product_start_fails(tmp_path, monkeypatch):
    (tmp_path / "current.jar").touch()
    monkeypatch.setattr(runner.java, "JAR", tmp_path / "current.jar")
    monkeypatch.setattr(lab, "free_port", lambda _: None)
    state = {"run_id": "synthetic", "origin": "http://localhost:18090"}
    monkeypatch.setattr(lab, "prepare", lambda *_: (tmp_path, state))
    monkeypatch.setattr(lab, "start", lambda *_: None)
    monkeypatch.setattr(runner.Trust, "load", lambda *_: SimpleNamespace(issuer="http://localhost:18090/realms/healthcare-iam-lab"))
    monkeypatch.setattr(runner, "operate", lambda *args: {})
    monkeypatch.setattr(runner.python, "startup", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("synthetic")))
    cleaned = []
    monkeypatch.setattr(runner, "cleanup", lambda *args: cleaned.append(True))
    with pytest.raises(OSError):
        runner.run()
    assert cleaned
    evidence = json.loads((tmp_path / "cross-service-failure.json").read_text())
    assert evidence["stage"] == "both_product_startups_before_token_issuance"
    assert "synthetic" not in evidence.values()
