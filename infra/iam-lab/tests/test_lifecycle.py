"""Offline ownership, cleanup and fixture-boundary tests. All Docker calls mocked."""
import json

import pytest

pytest.importorskip("jwt")
import lab


def test_prepare_has_unique_secrets_and_sanitized_source(tmp_path, monkeypatch):
    monkeypatch.setattr(lab, "RUNTIME", tmp_path)
    monkeypatch.setattr(lab, "free_port", lambda _: None)
    monkeypatch.setattr(lab, "local_engine", lambda: None)
    monkeypatch.setattr(lab, "inventory", lambda: {"container": [], "volume": [], "network": []})
    first, state = lab.prepare(18090, 18190)
    second, _ = lab.prepare(18090, 18190)
    one, two = lab.read(first / "secrets.json"), lab.read(second / "secrets.json")
    values = [one["bootstrap"], *one["clients"].values(), *one["humans"].values()]
    assert len(set(values)) == 8
    assert set(values).isdisjoint([two["bootstrap"], *two["clients"].values(), *two["humans"].values()])
    sources = "".join((lab.ROOT / file).read_text() for file in ("compose.yaml", "realm.json", "policy.json"))
    assert all(value not in sources and value not in (first / "compose.env").read_text() for value in values)
    assert lab.state_for(state["run_id"])[1] == state
    template = lab.read(lab.ROOT / "realm.json")
    assert all("secret" not in client for client in template["clients"])
    assert all("credentials" not in user for user in template["users"])
    for directory in (first, second):
        for name in lab.SECRET_FILES:
            (directory / name).unlink(missing_ok=True)


@pytest.mark.parametrize("identity", ["..", "a/../b", "A" * 32, "a" * 31, "a" * 33])
def test_unsafe_run_id(identity):
    with pytest.raises(lab.Denied, match="invalid_run_id"):
        lab.run_dir(identity)


def state():
    return {"run_id": "a" * 32, "workspace": lab.WORKSPACE, "project": "iam-lab-" + "a" * 32,
            "baseline": {"container": ["preexisting-id"], "volume": [], "network": []},
            "owned": {"container": ["own-id"], "volume": [], "network": []}}


def labels(s):
    return {lab.LABEL + "owner": "iam-lab-v1", lab.LABEL + "workspace": lab.WORKSPACE,
            lab.LABEL + "run": s["run_id"], "com.docker.compose.project": s["project"]}


def test_preexisting_id_never_inspected_or_deleted(monkeypatch):
    monkeypatch.setattr(lab, "docker", lambda *a, **kw: pytest.fail("Docker must not be called"))
    with pytest.raises(lab.Denied, match="preexisting_resource_protected"):
        lab.inspect_owned(state(), "container", "preexisting-id")


@pytest.mark.parametrize("field", ["owner", "workspace", "run", "project"])
def test_every_ownership_label_required(field):
    s = state()
    values = labels(s)
    del values["com.docker.compose.project" if field == "project" else lab.LABEL + field]
    with pytest.raises(lab.Denied, match="resource_ownership_mismatch"):
        lab.owned_labels(s, values)


def test_container_identity_cannot_be_a_name_alias(monkeypatch):
    s = state()
    monkeypatch.setattr(lab, "docker", lambda *a, **kw: [{"Id": "different-id", "Config": {"Labels": labels(s)}}])
    with pytest.raises(lab.Denied, match="resource_identity_mismatch"):
        lab.inspect_owned(s, "container", "own-id")


def test_cleanup_only_recorded_verified_ids(tmp_path, monkeypatch):
    s = state()
    calls = []
    monkeypatch.setattr(lab, "local_engine", lambda: None)
    monkeypatch.setattr(lab, "record_owned", lambda *args: None)
    monkeypatch.setattr(lab, "inventory", lambda: {"container": ["own-id", "preexisting-id"], "volume": [], "network": []})
    monkeypatch.setattr(lab, "inspect_owned", lambda *args: {"Config": {"Labels": labels(s)}})
    monkeypatch.setattr(lab, "docker", lambda *args, **kw: calls.append(args))
    lab.cleanup(tmp_path, s)
    assert calls == [("stop", "--time", "15", "own-id"), ("rm", "own-id")]
    assert s["phase"] == "cleaned"
    calls.clear()
    monkeypatch.setattr(lab, "inventory", lambda: {"container": [], "volume": [], "network": []})
    lab.cleanup(tmp_path, s)
    assert calls == []


def test_cleanup_refuses_ownership_mismatch_before_stop(tmp_path, monkeypatch):
    monkeypatch.setattr(lab, "local_engine", lambda: None)
    monkeypatch.setattr(lab, "record_owned", lambda *args: None)
    monkeypatch.setattr(lab, "inventory", lambda: {"container": ["own-id"], "volume": [], "network": []})
    def inspect(*args):
        raise lab.Denied("resource_ownership_mismatch")
    monkeypatch.setattr(lab, "inspect_owned", inspect)
    monkeypatch.setattr(lab, "docker", lambda *args, **kw: pytest.fail("No Docker mutations permitted"))
    with pytest.raises(lab.Denied, match="resource_ownership_mismatch"):
        lab.cleanup(tmp_path, state())


def test_reimport_existing_run_denied(tmp_path):
    with pytest.raises(lab.Denied, match="fresh_run_required_no_reimport"):
        lab.start(tmp_path, {"phase": "running"})


def test_cleanup_volume_used_by_other_container_is_preserved(tmp_path, monkeypatch):
    s = state()
    s["owned"] = {"container": [], "volume": ["own-volume"], "network": []}
    monkeypatch.setattr(lab, "local_engine", lambda: None)
    monkeypatch.setattr(lab, "record_owned", lambda *args: None)
    monkeypatch.setattr(lab, "inventory", lambda: {"container": [], "volume": ["own-volume"], "network": []})
    monkeypatch.setattr(lab, "inspect_owned", lambda *args: {})
    calls = []
    def docker(*args, **kw):
        calls.append(args)
        return "foreign-container"
    monkeypatch.setattr(lab, "docker", docker)
    with pytest.raises(lab.Denied, match="volume_still_in_use"):
        lab.cleanup(tmp_path, s)
    assert calls == [("ps", "-aq", "--filter", "volume=own-volume")]


def test_fixture_has_exact_flows_audiences_and_no_role_imports():
    realm = lab.read(lab.ROOT / "realm.json")
    clients = {c["clientId"]: c for c in realm["clients"]}
    human = clients[lab.WEB]
    assert human["publicClient"] and human["standardFlowEnabled"]
    assert human["attributes"]["pkce.code.challenge.method"] == "S256"
    assert human["redirectUris"] == ["http://127.0.0.1:18190/callback"]
    assert all(not c["directAccessGrantsEnabled"] and not c["implicitFlowEnabled"] and not c["fullScopeAllowed"] for c in clients.values())
    assert not human["serviceAccountsEnabled"]
    assert clients["lab-ai-workload"]["defaultClientScopes"] == ["basic", "iam-ai"]
    assert clients["lab-python-to-java"]["defaultClientScopes"] == ["basic", "iam-interop"]
    assert all(c["optionalClientScopes"] == [] for c in clients.values())
    assert "roles" not in realm and "groups" not in realm


def test_human_fixture_has_synthetic_profile_without_email_identity_binding():
    realm = lab.read(lab.ROOT / "realm.json")
    policy = lab.read(lab.ROOT / "policy.json")
    humans = [user for user in realm["users"] if "serviceAccountClientId" not in user]
    assert len(humans) == 4
    for user in humans:
        assert user["firstName"] == "Synthetic" and user["lastName"]
        assert user["email"] == user["username"] + "@example.invalid"
        assert user["emailVerified"] is False
        assert user["id"] in policy["humans"]
        assert user["email"] not in policy["humans"]


@pytest.mark.parametrize("failure", ["stopped", "image", "wildcard", "unpublished"])
def test_http_requires_own_running_pinned_loopback_container(monkeypatch, failure):
    s = state()
    s["port"] = 18090
    ports = {"8080/tcp": [{"HostIp": "127.0.0.1", "HostPort": "18090"}]}
    item = {"State": {"Running": True}, "Config": {"Image": lab.IMAGE},
            "HostConfig": {"PortBindings": ports}, "NetworkSettings": {"Ports": ports}}
    if failure == "stopped":
        item["State"]["Running"] = False
    elif failure == "image":
        item["Config"]["Image"] = "unapproved-image"
    elif failure == "wildcard":
        item["HostConfig"]["PortBindings"] = {"8080/tcp": [{"HostIp": "0.0.0.0", "HostPort": "18090"}]}
    else:
        item["NetworkSettings"]["Ports"] = {"8080/tcp": []}
    monkeypatch.setattr(lab, "inspect_owned", lambda *args: item)
    with pytest.raises(lab.Denied):
        lab.running_container(s)


def test_ambient_compose_variables_cannot_override_ownership(monkeypatch):
    monkeypatch.setenv("IAM_LAB_RUN_DIR", "untrusted-path")
    monkeypatch.setenv("COMPOSE_PROJECT_NAME", "foreign-project")
    def subprocess_run(command, **kwargs):
        assert "IAM_LAB_RUN_DIR" not in kwargs["env"]
        assert "COMPOSE_PROJECT_NAME" not in kwargs["env"]
        return type("Result", (), {"returncode": 0, "stdout": ""})()
    monkeypatch.setattr(lab.subprocess, "run", subprocess_run)
    lab.docker("compose", "version")
