"""Offline policy lifecycle/concurrency checks using real signed JWTs and SQLite."""
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.config import Settings
from app.oidc_config import PERMISSION, ROUTE, Rejected
from app.oidc_verifier import AccessVerifier, KeyCache
from app.oidc_workload import WorkloadBoundary, configure_boundary
from app.trusted_identity_registry import RegistryError, TrustedIdentityRegistry, load_fixture
from app.trusted_identity_registry_cli import main as cli
from tests.test_oidc_workload import SUBJECT, config, fetcher, registration, token

SERVICE = Path(__file__).resolve().parents[1]
PRINCIPAL = "fixture-ai-workload"
ORG = "org-lab-a"


@pytest.fixture(scope="module")
def registry_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def fixture_data():
    return json.loads((SERVICE / "trusted-identity-registry.example.json").read_text(encoding="utf-8"))


def initialize(tmp_path, data=None):
    fixture_path = tmp_path / "fixture.json"
    fixture_path.write_text(json.dumps(fixture_data() if data is None else data), encoding="utf-8")
    registry = TrustedIdentityRegistry(str(tmp_path / "registry.sqlite"))
    registry.initialize(load_fixture(fixture_path), "synthetic-operator")
    return registry


@pytest.fixture
def registry(tmp_path):
    return initialize(tmp_path)


@pytest.fixture
def dynamic(tmp_path, registry, registry_key):
    data = registration()
    data["allowed_organization_ids"] = [ORG, "org-lab-b"]
    # No static identity can accidentally satisfy a dynamic decision.
    data["bindings"] = []
    path = tmp_path / "trust.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    boundary = WorkloadBoundary(str(path), str(tmp_path / "audit.sqlite"), policy_mode="sqlite", registry_path=str(registry.path))
    boundary.verifier = AccessVerifier(boundary.config, KeyCache(boundary.config, fetcher(registry_key)))
    app = FastAPI()
    @app.get(ROUTE)
    def endpoint(request: Request):
        return boundary.handle(request)
    with TestClient(app) as client:
        yield registry, boundary, client, token(registry_key), tmp_path / "audit.sqlite"


def request(dynamic, expected=200, organization=None):
    _, _, client, encoded, _ = dynamic
    headers = {"Authorization": "Bearer " + encoded}
    if organization is not None:
        headers["X-IAM-Lab-Organization"] = organization
    response = client.get(ROUTE, headers=headers)
    assert response.status_code == expected
    if expected != 200:
        assert "internal_principal_id" not in response.text
    return response


def change_rows(registry):
    with registry.connection() as connection:
        return connection.execute("SELECT revision,operation,operator_kind,operator_verified FROM registry_policy_change_audit ORDER BY revision").fetchall()


def test_clean_init_and_minimized_list(registry):
    listing = registry.sanitized()
    assert listing["revision"] == 1 and listing["operator_verified"] is False
    assert listing["principals"] == [(PRINCIPAL, "workload", 1, 1)]
    assert SUBJECT not in json.dumps(listing) and "issuer" not in listing
    assert change_rows(registry) == [(1, "init", "local_operator_unverified", 0)]


def test_repeated_init_never_overwrites(registry):
    before = registry.path.read_bytes()
    with pytest.raises(RegistryError, match="registry_already_exists"):
        registry.initialize(load_fixture(SERVICE / "trusted-identity-registry.example.json"))
    assert registry.path.read_bytes() == before
    assert registry.sanitized()["revision"] == 1


@pytest.mark.parametrize("damage", ["schema", "version", "application", "missing_metadata", "audit_gap", "foreign_table"])
def test_invalid_schema_fails_closed(dynamic, damage):
    registry, _, _, _, _ = dynamic
    with closing(sqlite3.connect(registry.path)) as connection:
        statements = {"schema": "DROP TABLE registry_permission", "version": "PRAGMA user_version=99",
                      "application": "PRAGMA application_id=0", "missing_metadata": "DELETE FROM registry_metadata",
                      "audit_gap": "DELETE FROM registry_policy_change_audit", "foreign_table": "CREATE TABLE foreign_store(id TEXT)"}
        connection.execute(statements[damage])
        connection.commit()
    request(dynamic, 503)


@pytest.mark.parametrize("invalid", ["duplicate_subject", "duplicate_client", "missing_principal", "missing_membership", "duplicate_membership"])
def test_fixture_constraints_reject_inconsistent_policy(tmp_path, invalid):
    data = fixture_data()
    if invalid.startswith("duplicate_") and invalid != "duplicate_membership":
        binding = dict(data["bindings"][0], binding_id="second-binding")
        binding["client_id" if invalid == "duplicate_subject" else "external_subject"] = "other-value"
        data["bindings"].append(binding)
    elif invalid == "missing_principal":
        data["bindings"][0]["principal_id"] = "missing"
    elif invalid == "missing_membership":
        data["memberships"] = []
    else:
        data["memberships"].append(data["memberships"][0])
    with pytest.raises(RegistryError):
        initialize(tmp_path, data)
    # Failed exclusive initialization is retained, but all schema/rows rolled back.
    with closing(sqlite3.connect(tmp_path / "registry.sqlite")) as connection:
        assert connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall() == []


@pytest.mark.parametrize("operation,restore,target,org,permission,status", [
    ("disable-principal", "enable-principal", PRINCIPAL, None, None, 401),
    ("disable-binding", "enable-binding", "binding-ai", None, None, 401),
    ("revoke-membership", "grant-membership", PRINCIPAL, ORG, None, 403),
    ("revoke-permission", "grant-permission", PRINCIPAL, ORG, PERMISSION, 403),
])
def test_same_valid_jwt_revocation_and_explicit_restore(dynamic, operation, restore, target, org, permission, status):
    registry, boundary, _, encoded, _ = dynamic
    assert request(dynamic).json()["organization_id"] == ORG
    expiry = boundary.verifier.verify(encoded).expires_at
    assert registry.mutate(operation, target, org, permission, "operator-local")["revision"] == 2
    assert boundary.verifier.verify(encoded).expires_at == expiry
    request(dynamic, status)
    reopened = TrustedIdentityRegistry(str(registry.path))
    assert reopened.sanitized()["revision"] == 2
    reopened.mutate(restore, target, org, permission)
    request(dynamic)
    assert [r[1] for r in change_rows(registry)] == ["init", operation, restore]


def test_multi_organization_explicit_selection_no_permission_union(dynamic):
    registry, _, _, _, _ = dynamic
    registry.mutate("grant-membership", PRINCIPAL, "org-lab-b")
    request(dynamic, 403)  # Never take the first membership.
    request(dynamic, organization=ORG)
    request(dynamic, 403, "org-lab-b")
    registry.mutate("grant-permission", PRINCIPAL, "org-lab-b", PERMISSION)
    registry.mutate("revoke-permission", PRINCIPAL, ORG, PERMISSION)
    request(dynamic, 403, ORG)
    assert request(dynamic, organization="org-lab-b").json()["effective_permissions"] == [PERMISSION]
    registry.mutate("revoke-membership", PRINCIPAL, "org-lab-b")
    request(dynamic, 403, "org-lab-b")


@pytest.mark.parametrize("headers", [
    [("X-IAM-Lab-Organization", ORG), ("X-IAM-Lab-Organization", ORG)],
    [("X-IAM-Lab-Organization", ORG + ",org-lab-b")],
    [("X-IAM-Lab-Organization", "")], [("X-IAM-Lab-Organization", " " + ORG)],
    [("X-IAM-Lab-Organization", "x" * 65)], [("X-IAM-Lab-Organization", "org-not-registered")],
])
def test_ambiguous_or_unknown_organization_is_not_authority(dynamic, headers):
    _, _, client, encoded, _ = dynamic
    assert client.get(ROUTE, headers=[("Authorization", "Bearer " + encoded), *headers]).status_code == 403


def test_authentication_precedes_organization_policy(dynamic):
    _, _, client, _, _ = dynamic
    response = client.get(ROUTE, headers={"Authorization": "Bearer a.b.c", "X-IAM-Lab-Organization": "invalid,ambiguous"})
    assert response.status_code == 401


def test_provider_allowed_org_still_bounds_registry(dynamic):
    registry, boundary, _, _, _ = dynamic
    registry.mutate("grant-membership", PRINCIPAL, "org-lab-b")
    registry.mutate("grant-permission", PRINCIPAL, "org-lab-b", PERMISSION)
    data = registration()
    boundary.config = config(data)  # Only A allowed by crypto trust configuration.
    request(dynamic, 403, "org-lab-b")


@pytest.mark.parametrize("damage", ["missing", "corrupt", "directory", "trust_mismatch"])
def test_unavailable_registry_never_falls_back_to_static(dynamic, damage, tmp_path):
    registry, boundary, _, _, _ = dynamic
    boundary.config = config()  # Static valid binding exists; must never be used.
    if damage == "missing":
        boundary.registry = TrustedIdentityRegistry(str(tmp_path / "absent.sqlite"))
    elif damage == "directory":
        boundary.registry = TrustedIdentityRegistry(str(tmp_path))
    elif damage == "corrupt":
        path = tmp_path / "corrupt.sqlite"
        path.write_bytes(b"not a SQLite database")
        boundary.registry = TrustedIdentityRegistry(str(path))
    else:
        with closing(sqlite3.connect(registry.path)) as connection:
            connection.execute("UPDATE registry_metadata SET issuer=?", ("https://other.example.invalid",))
            connection.commit()
    request(dynamic, 503)


def test_registry_sqlite_write_lock_returns_503(dynamic):
    registry, _, _, _, _ = dynamic
    with closing(sqlite3.connect(registry.path)) as connection:
        connection.execute("BEGIN EXCLUSIVE")
        # WAL readers remain valid while writer uncommitted; no promise of aborting an old decision.
        request(dynamic)
        with pytest.raises(RegistryError):
            registry.mutate("disable-principal", PRINCIPAL)
        connection.rollback()
    request(dynamic)
    assert registry.sanitized()["revision"] == 1


def test_policy_change_audit_failure_rolls_back_everything(registry, monkeypatch):
    def failed(*_):
        raise RegistryError("policy_audit_unavailable")
    monkeypatch.setattr(registry, "append_change", failed)
    with pytest.raises(RegistryError):
        registry.mutate("disable-principal", PRINCIPAL)
    reopened = TrustedIdentityRegistry(str(registry.path))
    assert reopened.sanitized()["principals"][0][2:] == (1, 1)
    assert len(change_rows(reopened)) == 1


def test_access_audit_storage_failure_returns_503(dynamic):
    _, boundary, _, _, _ = dynamic
    request(dynamic)
    with closing(sqlite3.connect(boundary.audit.path)) as connection:
        connection.execute("BEGIN IMMEDIATE")
        request(dynamic, 503)
        connection.rollback()


def test_actual_change_audit_constraint_failure_rolls_back(registry, monkeypatch):
    def failed(connection, *_):
        connection.execute("INSERT INTO registry_policy_change_audit SELECT * FROM registry_policy_change_audit LIMIT 1")
    monkeypatch.setattr(registry, "append_change", failed)
    with pytest.raises(RegistryError, match="registry_unavailable"):
        registry.mutate("disable-principal", PRINCIPAL)
    assert registry.sanitized()["principals"][0][2:] == (1, 1)
    assert len(change_rows(registry)) == 1


def test_registry_read_sqlite_failure_is_503(dynamic, monkeypatch):
    _, boundary, _, _, _ = dynamic
    def failed(*_):
        raise sqlite3.OperationalError("synthetic unavailable storage")
    monkeypatch.setattr(boundary.registry, "validate", failed)
    request(dynamic, 503)


@pytest.mark.parametrize("change", ["subject", "client", "issuer"])
def test_valid_signed_unregistered_identity_is_401(dynamic, registry_key, change):
    _, _, client, _, _ = dynamic
    changes = {"subject": {"sub": "unregistered"}, "client": {"azp": "unregistered"},
               "issuer": {"iss": "https://untrusted.example.invalid"}}[change]
    assert client.get(ROUTE, headers={"Authorization": "Bearer " + token(registry_key, **changes)}).status_code == 401


def test_disabled_organization_provides_no_access(tmp_path, registry_key):
    data = fixture_data()
    data["organizations"][0]["enabled"] = False
    registry = initialize(tmp_path, data)
    verified = type("Verified", (), {"subject": SUBJECT, "client_id": "lab-ai-workload"})()
    with pytest.raises(Rejected) as error:
        registry.resolve(config(), verified, ORG)
    assert error.value.status == 403


@pytest.mark.parametrize("invalid", ["duplicate_json", "oversize", "wrong_type", "human_principal"])
def test_fixture_bounded_closed_validation(tmp_path, invalid):
    data = fixture_data()
    raw = json.dumps(data)
    if invalid == "duplicate_json":
        raw = raw.replace('"contract_version":', '"contract_version":"other","contract_version":', 1)
    elif invalid == "oversize":
        raw = " " * 1048577
    elif invalid == "wrong_type":
        data["principals"][0]["enabled"] = "true"
        raw = json.dumps(data)
    else:
        data["principals"][0]["principal_type"] = "human"
        raw = json.dumps(data)
    path = tmp_path / "invalid.json"
    path.write_text(raw, encoding="utf-8")
    with pytest.raises(RegistryError, match="invalid_fixture"):
        load_fixture(path)


def test_policy_access_audits_are_separate_and_minimized(dynamic):
    registry, _, _, _, path = dynamic
    request(dynamic)
    registry.mutate("revoke-permission", PRINCIPAL, ORG, PERMISSION)
    request(dynamic, 403)
    with closing(sqlite3.connect(path)) as connection:
        events = connection.execute("SELECT outcome,actor_id,organization_id,reason_code FROM oidc_workload_security_audit_v1 ORDER BY timestamp_utc").fetchall()
    assert events == [("allowed", PRINCIPAL, ORG, "access_granted"), ("denied", None, None, "policy_rejected")]
    with registry.connection() as connection:
        changes = connection.execute("SELECT * FROM registry_policy_change_audit").fetchall()
    assert SUBJECT not in json.dumps(changes) and "Bearer" not in json.dumps(changes)


def test_lifespan_dynamic_mode_real_main_and_legacy_unchanged(tmp_path, registry, registry_key, monkeypatch):
    from app.main import app, get_settings
    from app import oidc_workload
    trust = tmp_path / "trust.json"
    trust.write_text(json.dumps(registration()), encoding="utf-8")
    settings = Settings("http://127.0.0.1:9", "/", 1, "synthetic-service-only", "127.0.0.1", 8090,
        ai_review_db_path=str(tmp_path / "review.sqlite"), human_session_db_path=str(tmp_path / "session.sqlite"),
        institutional_knowledge_db_path=str(tmp_path / "knowledge.sqlite"),
        security_audit_db_path=str(tmp_path / "legacy-audit.sqlite"), oidc_workload_lab_enabled=True,
        oidc_workload_policy_mode="sqlite", oidc_workload_registry_db_path=str(registry.path),
        oidc_workload_trust_config_path=str(trust), oidc_workload_audit_db_path=str(tmp_path / "access.sqlite"))
    monkeypatch.setattr("app.main.get_settings", lambda: settings)
    monkeypatch.setattr(oidc_workload, "AccessVerifier", lambda cfg: AccessVerifier(cfg, KeyCache(cfg, fetcher(registry_key))))
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        with TestClient(app) as client:
            encoded = token(registry_key)
            assert client.get(ROUTE, headers={"Authorization": "Bearer " + encoded}).status_code == 200
            registry.mutate("disable-principal", PRINCIPAL)
            assert client.get(ROUTE, headers={"Authorization": "Bearer " + encoded}).status_code == 401
            assert client.get("/internal/agent-context", headers={"Authorization": "Bearer " + encoded}).status_code == 401
        disabled = replace_settings(settings, oidc_workload_lab_enabled=False)
        configure_boundary(app, disabled)
        assert ROUTE not in app.openapi()["paths"]
    finally:
        app.dependency_overrides.pop(get_settings, None)
        configure_boundary(app, replace_settings(settings, oidc_workload_lab_enabled=False))


def replace_settings(settings, **values):
    from dataclasses import replace
    return replace(settings, **values)


def test_read_snapshot_and_confirmed_revocation_boundary(dynamic):
    registry, boundary, client, encoded, _ = dynamic
    with registry.connection() as old_snapshot:
        assert old_snapshot.execute("SELECT enabled FROM registry_permission").fetchone()[0] == 1
        with ThreadPoolExecutor(max_workers=1) as pool:
            result = pool.submit(registry.mutate, "revoke-permission", PRINCIPAL, ORG, PERMISSION).result(timeout=5)
        assert result["committed"] is True
        assert old_snapshot.execute("SELECT enabled FROM registry_permission").fetchone()[0] == 1
        # Fresh requests are denied although a reader whose snapshot predates commit remains unchanged.
        with ThreadPoolExecutor(max_workers=8) as pool:
            statuses = list(pool.map(lambda _: client.get(ROUTE, headers={"Authorization": "Bearer " + encoded}).status_code, range(16)))
        assert statuses == [403] * 16
    assert boundary.verifier.verify(encoded).expires_at > 0


def test_concurrent_mutations_serialize_with_atomic_audit(registry):
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: registry.mutate("grant-permission", PRINCIPAL, ORG, PERMISSION), range(12)))
    assert sorted(r["revision"] for r in results) == list(range(2, 14))
    assert len(change_rows(registry)) == 13


def test_claims_headers_json_cannot_change_registry(dynamic, registry_key):
    registry, _, client, _, _ = dynamic
    registry.mutate("revoke-permission", PRINCIPAL, ORG, PERMISSION)
    malicious = token(registry_key, roles=[PERMISSION], organization=ORG, permissions=[PERMISSION],
                      principal={"enabled": True, "internal_principal_id": PRINCIPAL})
    response = client.request("GET", ROUTE, headers={"Authorization": "Bearer " + malicious,
        "X-Principal-ID": PRINCIPAL, "X-Organization-ID": ORG}, json={"operation": "grant-permission", "permission": PERMISSION})
    assert response.status_code == 403 and registry.sanitized()["revision"] == 2


@pytest.mark.parametrize("target,organization,permission", [("missing", ORG, None), (PRINCIPAL, "missing", None),
    ("'; DROP TABLE registry_principal;--", ORG, None), (PRINCIPAL, ORG, "*"), (PRINCIPAL, ORG, "x" * 81)])
def test_mutation_inputs_or_foreign_keys_reject_without_change(registry, target, organization, permission):
    operation = "grant-membership" if permission is None else "grant-permission"
    with pytest.raises(RegistryError):
        registry.mutate(operation, target, organization, permission)
    assert registry.sanitized()["revision"] == 1


def test_cli_init_mutate_list_and_errors(tmp_path, capsys):
    db = str(tmp_path / "cli.sqlite")
    assert cli(["init", "--db", db, "--fixture", str(SERVICE / "trusted-identity-registry.example.json")]) == 0
    assert cli(["revoke-permission", "--db", db, "--target", PRINCIPAL, "--organization", ORG, "--permission", PERMISSION]) == 0
    assert cli(["list", "--db", db]) == 0
    assert SUBJECT not in capsys.readouterr().out
    assert cli(["init", "--db", db, "--fixture", str(SERVICE / "trusted-identity-registry.example.json")]) == 1
    assert cli(["disable-principal", "--db", db, "--target", PRINCIPAL, "--organization", ORG]) == 1
    assert cli(["list", "--db", "relative.sqlite"]) == 1
    assert cli(["unknown-sensitive-value", "--db", db]) == 1
    assert "unknown-sensitive-value" not in capsys.readouterr().err


def test_disabled_lifecycle_has_no_registry_io(tmp_path, monkeypatch):
    settings = Settings("http://127.0.0.1:9", "/", 1, "", "127.0.0.1", 8090,
                        oidc_workload_policy_mode="sqlite", oidc_workload_registry_db_path=str(tmp_path / "absent.sqlite"))
    monkeypatch.setattr(TrustedIdentityRegistry, "__init__", lambda *_: pytest.fail("No registry I/O when disabled"))
    app = FastAPI()
    configure_boundary(app, settings)
    with TestClient(app) as client:
        assert client.get(ROUTE).status_code == 404 and ROUTE not in client.get("/openapi.json").json()["paths"]


def test_modes_default_and_invalid_fail_closed(dynamic, monkeypatch):
    monkeypatch.delenv("OIDC_WORKLOAD_POLICY_MODE", raising=False)
    assert Settings.from_env().oidc_workload_policy_mode == "static"
    _, boundary, _, _, _ = dynamic
    boundary.policy_mode = "invalid"
    request(dynamic, 503)


@pytest.mark.parametrize("store", ["review", "session", "knowledge", "legacy-audit", "oidc-audit", "agent-workflow"])
def test_registry_refuses_other_store_paths(tmp_path, store):
    path = str(tmp_path / (store + ".sqlite"))
    with pytest.raises(RegistryError, match="separate_registry_required"):
        TrustedIdentityRegistry(path, (path,))


def test_static_single_org_backward_compatible_and_candidate_revalidated(tmp_path, registry_key):
    trust = tmp_path / "trust.json"
    trust.write_text(json.dumps(registration()), encoding="utf-8")
    boundary = WorkloadBoundary(str(trust), str(tmp_path / "audit.sqlite"))
    boundary.verifier = AccessVerifier(boundary.config, KeyCache(boundary.config, fetcher(registry_key)))
    app = FastAPI()
    @app.get(ROUTE)
    def endpoint(request: Request):
        return boundary.handle(request)
    with TestClient(app) as client:
        headers = {"Authorization": "Bearer " + token(registry_key)}
        assert client.get(ROUTE, headers=headers).status_code == 200
        assert client.get(ROUTE, headers={**headers, "X-IAM-Lab-Organization": ORG}).status_code == 200
        assert client.get(ROUTE, headers={**headers, "X-IAM-Lab-Organization": "org-lab-b"}).status_code == 403
