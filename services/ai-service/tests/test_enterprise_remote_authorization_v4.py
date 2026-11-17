"""V4 binding columns. The operational gateway is not retargeted by this migration."""
from datetime import timedelta
from pathlib import Path
import inspect
import socket
import sqlite3

import pytest

from app.enterprise_ai_processing.execution_types import ExecutionError
from app.enterprise_ai_processing.remote_authorization import (
    BUDGET_CEILING_MAX_MICROUSD, RESERVATION_MICROUSD, RemoteAuthorization,
)
from app.enterprise_ai_processing.sqlite_ledger import MIGRATION_V4, SQLiteExecutionLedger
from app.enterprise_llm_providers.errors import ProviderError
from app.enterprise_llm_providers.gemini_configuration import GeminiSettings
from app.enterprise_llm_providers.gemini_request import build_generation
from app.enterprise_llm_providers.gemini_transport import GeminiSDKTransport
from app.enterprise_llm_providers.live_smoke import LABORATORY_CAP_MICROUSD
from app.enterprise_llm_providers.request import build_payload
from app.enterprise_llm_providers.smoke import FIXED_DOCUMENT
from app.enterprise_llm_providers.transport import OpenAISDKTransport, live_egress_enabled
from app.enterprise_llm_providers.configuration import ProviderSettings
from app.model_gateway.gateway import NeutralModelGateway
from app.model_gateway.registry import lab_catalog
from tests.enterprise_ai_processing_execution_fixture import execution_laboratory


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("provider socket forbidden")

    monkeypatch.setattr(socket, "socket", forbidden)


def _ready(tmp_path):
    lab = execution_laboratory(tmp_path)
    lab.ledger.migrate_to_v2(lab.admin["ORG-A"])
    lab.ledger.migrate_to_v3(lab.admin["ORG-A"])
    return lab


def _record(lab, **overrides):
    now = lab.clock()
    values = dict(
        authorization_id="remote-v4-a", organization_id="ORG-A", deployment_id="openai-offline-a",
        provider_id="openai", model_id="gpt-6-luna", valid_from=now - timedelta(minutes=1),
        expires_at=now + timedelta(minutes=5), principal_id="synthetic-executor",
        resource_id="vacation-a", budget_ceiling_microusd=1000)
    values.update(overrides)
    return RemoteAuthorization(**values)


def _columns(path):
    with sqlite3.connect(path) as connection:
        return [row[1] for row in connection.execute("PRAGMA table_info(aip_remote_execution_permit)")]


def test_catalog_ceilings_match_the_closed_reservations():
    found = {item.deployment_id: item.reservation_microusd for item in lab_catalog()}
    for deployment_id, reservation in RESERVATION_MICROUSD.items():
        assert found[deployment_id] == reservation
    assert BUDGET_CEILING_MAX_MICROUSD == LABORATORY_CAP_MICROUSD == 5_000_000
    assert "budget_exceeded" not in MIGRATION_V4.read_text(encoding="utf-8")


def test_v4_migration_is_explicit_and_stores_the_binding(tmp_path):
    lab = _ready(tmp_path)
    lab.ledger.evaluate_remote_authorization(lab.executor["ORG-A"], _record(lab, principal_id=None,
        resource_id=None, budget_ceiling_microusd=None))
    root, issuer, clock = lab.ledger.root, lab.issuer, lab.clock
    lab.close()
    reopened = SQLiteExecutionLedger(root, issuer, clock)
    try:
        with sqlite3.connect(reopened.path) as connection:
            assert connection.execute("SELECT schema_version FROM aip_store").fetchone()[0] == 3
        reopened.migrate_to_v4(issuer.issue("ORG-A"))
        with sqlite3.connect(reopened.path) as connection:
            assert connection.execute("SELECT schema_version,contract FROM aip_store").fetchone() == (
                4, "enterprise-ai-processing-ledger-v4")
            assert connection.execute("SELECT count(*) FROM aip_remote_authorization_audit").fetchone()[0] == 1
        record = _record(lab)
        reopened.register_remote_authorization(issuer.issue("ORG-A"), record)
        decision = reopened.evaluate_remote_authorization(issuer.issue("ORG-A", "executor"), record)
        assert decision.allowed is True and decision.egress_allowed is False
        assert decision.live_authorized is False and decision.c03_connected is False
        with sqlite3.connect(reopened.path) as connection:
            row = connection.execute(
                "SELECT principal_id,resource_id,budget_ceiling_microusd,status FROM aip_remote_execution_permit"
            ).fetchone()
        assert row == ("synthetic-executor", "vacation-a", 1000, "active")
        with pytest.raises(ExecutionError) as repeated:
            reopened.migrate_to_v4(issuer.issue("ORG-A"))
        assert repeated.value.reason == "revision_conflict"
    finally:
        reopened.close()


def test_invalid_binding_and_money_are_rejected(tmp_path):
    lab = _ready(tmp_path)
    lab.ledger.migrate_to_v4(lab.admin["ORG-A"])
    with pytest.raises(ExecutionError) as missing:
        lab.ledger.register_remote_authorization(lab.admin["ORG-A"], _record(
            lab, principal_id=None, resource_id=None, budget_ceiling_microusd=None))
    assert missing.value.reason == "invalid_input"
    for ceiling in (190, 0, -1, True, 5_000_001, "1000"):
        with pytest.raises(ExecutionError) as money:
            lab.ledger.register_remote_authorization(lab.admin["ORG-A"], _record(
                lab, authorization_id="remote-money", budget_ceiling_microusd=ceiling))
        assert money.value.reason == "invalid_input"
    with pytest.raises(ExecutionError) as blank:
        lab.ledger.register_remote_authorization(lab.admin["ORG-A"], _record(lab, resource_id=""))
    assert blank.value.reason == "invalid_input"
    lab.ledger.register_remote_authorization(lab.admin["ORG-A"], _record(lab, budget_ceiling_microusd=191))
    lab.ledger.register_remote_authorization(lab.admin["ORG-A"], _record(
        lab, authorization_id="remote-v4-b", resource_id="vacation-b"))
    with pytest.raises(ExecutionError) as duplicate:
        lab.ledger.register_remote_authorization(lab.admin["ORG-A"], _record(
            lab, authorization_id="remote-v4-c"))
    assert duplicate.value.reason == "revision_conflict"
    with sqlite3.connect(lab.ledger.path) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO aip_remote_execution_permit VALUES "
                "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                ("remote-raw", "ORG-A", "openai-sdk-a", "openai", "gpt-6-luna", "vacation-days-v1",
                 "structured_output+usage_report", "model-gateway-policy-v1", 1, "active",
                 1, 2, 1, "synthetic-administrator", None, None, None,
                 "synthetic-executor", "vacation-a", 1))
    lab.close()


def test_v3_rows_block_migration_without_a_partial_schema(tmp_path):
    lab = _ready(tmp_path)
    record = _record(lab, principal_id=None, resource_id=None, budget_ceiling_microusd=None,
                     authorization_id="remote-v3")
    lab.ledger.register_remote_authorization(lab.admin["ORG-A"], record)
    with pytest.raises(ExecutionError) as blocked:
        lab.ledger.migrate_to_v4(lab.admin["ORG-A"])
    assert blocked.value.reason == "revision_conflict"
    with sqlite3.connect(lab.ledger.path) as connection:
        assert connection.execute("SELECT schema_version FROM aip_store").fetchone()[0] == 3
        assert connection.execute("SELECT count(*) FROM aip_remote_execution_permit").fetchone()[0] == 1
    assert "principal_id" not in _columns(lab.ledger.path)
    with pytest.raises(ExecutionError) as early:
        lab.ledger.register_remote_authorization(lab.admin["ORG-A"], _record(lab))
    assert early.value.reason == "invalid_input"

    def fail(stage):
        if stage == "migrate_v4_before_commit":
            raise OSError("disk")

    (tmp_path / "empty").mkdir()
    empty = _ready(tmp_path / "empty")
    empty.ledger._fault = fail
    with pytest.raises(ExecutionError) as failed:
        empty.ledger.migrate_to_v4(empty.admin["ORG-A"])
    assert failed.value.unavailable is True
    with sqlite3.connect(empty.ledger.path) as connection:
        assert connection.execute("SELECT schema_version FROM aip_store").fetchone()[0] == 3
    assert "principal_id" not in _columns(empty.ledger.path)
    empty.ledger._fault = lambda stage: None
    empty.ledger.migrate_to_v4(empty.admin["ORG-A"])
    with sqlite3.connect(empty.ledger.path) as connection:
        assert connection.execute("SELECT schema_version FROM aip_store").fetchone()[0] == 4
        assert connection.execute("SELECT count(*) FROM aip_remote_execution_permit").fetchone()[0] == 0
    lab.close()
    empty.close()


def test_gateway_contract_and_transports_stay_closed(tmp_path):
    signature = inspect.signature(NeutralModelGateway.execute)
    assert tuple(signature.parameters) == (
        "self", "access", "authorization_id", "budget_microusd", "resource_id",
        "deployment_id", "supplied_url", "operation_id", "egress_consent")
    assert signature.parameters["egress_consent"].default is None
    gateway = Path(__file__).resolve().parents[1] / "app" / "model_gateway" / "gateway.py"
    agent = Path(__file__).resolve().parents[1] / "app" / "model_gateway" / "agent.py"
    processing = Path(__file__).resolve().parents[1] / "app" / "enterprise_ai_processing" / "gateway.py"
    gateway_text = gateway.read_text(encoding="utf-8")
    assert "migrate_to_v4" not in gateway_text and "OfflineModelHarness" not in gateway_text
    assert "type(self._resolver) is not LedgerDurableAuthorization" in gateway_text
    assert "type(gateway) is not NeutralModelGateway" in agent.read_text(encoding="utf-8")
    assert "type(self.model) is FakeEnterpriseModel" in processing.read_text(encoding="utf-8")
    assert live_egress_enabled() is False
    settings = ProviderSettings(True, "gpt-6-luna", 15, 256, 2048, 1000, 5_000_000, "sk-lab-not-a-real-key")
    with pytest.raises(ProviderError) as openai_blocked:
        OpenAISDKTransport("sk-lab-not-a-real-key").send(build_payload(FIXED_DOCUMENT, settings), 15)
    gemini_settings = GeminiSettings(True, "gemini-3.5-flash-lite", 15, 128, 2048, 1000, "test-gemini-marker")
    with pytest.raises(ProviderError) as gemini_blocked:
        GeminiSDKTransport("test-gemini-marker").send(build_generation(FIXED_DOCUMENT, gemini_settings), 15)
    assert openai_blocked.value.reason == gemini_blocked.value.reason == "egress_blocked"
    lab = _ready(tmp_path)
    with sqlite3.connect(lab.ledger.path) as connection:
        assert connection.execute("SELECT schema_version FROM aip_store").fetchone()[0] == 3
    lab.close()
