"""TEST ONLY C02 issuer/composition; never product authentication or an API."""
from dataclasses import replace
from datetime import timedelta

from app.enterprise_ai_processing.execution_types import LaboratoryAccess
from app.enterprise_ai_processing.gateway import EnterpriseModelGateway
from app.enterprise_ai_processing.sqlite_ledger import SQLiteExecutionLedger
from app.enterprise_connectors.synthetic import SyntheticPage
from tests.enterprise_ai_processing_fixture import processing_laboratory


CLAUSE = "VACACIONES: 20 dias tras 12 meses de servicio. Solo documento sintetico."


class TestAccessAuthority:
    __test__ = False

    def __init__(self, clock):
        self.clock, self.issued = clock, {}

    def issue(self, org="ORG-A", role="administrator", **changes):
        context = LaboratoryAccess("synthetic-" + role, org, role, self.clock() + timedelta(minutes=5))
        context = replace(context, **changes)
        self.issued[id(context)] = context
        return context

    def recognizes(self, context):
        return self.issued.get(id(context)) is context


class ExecutionFixture:
    def __init__(self, root, *, text=CLAUSE):
        self.source = processing_laboratory()
        self.connector, self.clock = self.source.connector, self.source.clock
        self.issuer = TestAccessAuthority(self.clock)
        self.admin = {org: self.issuer.issue(org) for org in ("ORG-A", "ORG-B")}
        self.executor = {org: self.issuer.issue(org, "executor") for org in self.admin}
        self.ledger = SQLiteExecutionLedger(root, self.issuer, self.clock)
        try:
            self.ledger.initialize(self.admin["ORG-A"])
            revision = 1
            for profile, grant in zip(self.source.policy.profiles, self.source.policy.grants):
                revision = self.ledger.change_policy(self.admin[profile.organization_id], profile, expected_revision=revision)
                revision = self.ledger.change_policy(self.admin[grant.organization_id], grant, expected_revision=revision,
                                                     approval_ref=grant.grant_id)
            self.connector.adapter.set_pages("vacation-a", (SyntheticPage(text),))
            self.connector.adapter.set_pages("vacation-b", (SyntheticPage(text),))
            self.gateway = EnterpriseModelGateway(self.ledger, self.connector.policy, self)
        except BaseException:
            self.ledger.close()
            raise
        finally:
            text = None

    def recognizes_envelope(self, envelope):
        return self.source.boundary.recognizes_envelope(envelope)

    def recognizes_source(self, evidence, envelope):
        return self.source.boundary.recognizes_source(evidence, envelope)

    def connector_snapshot(self):
        return self.connector.store.snapshot()

    def authority(self, owner):
        return self.executor[owner.envelope.context.organization_id]

    def populate(self, owner):
        try:
            owner.source_bytes = self.source.boundary.sources[id(owner.evidence)].document.text.encode("utf-8")
            owner.question_bytes = owner.envelope.question.encode("utf-8")
        finally:
            owner = None

    def mint(self, suffix="a", **overrides):
        with self.ledger.barrier:
            envelope, evidence = self.source.issue(suffix, **overrides)
            policy = self.ledger.policy(self.executor[envelope.context.organization_id])
            envelope = self.source.boundary.remember(replace(envelope, processing_revision=policy.revision))
            return envelope, evidence

    def prepare(self, suffix="a", **overrides):
        return self.gateway.prepare(*self.mint(suffix, **overrides))

    def change_grant(self, suffix="a", **overrides):
        org = "ORG-A" if suffix == "a" else "ORG-B"
        with self.ledger.barrier:
            policy = self.ledger.policy(self.executor[org])
            grant = replace(policy.grants[0], version=policy.grants[0].version + 1, **overrides)
            return self.ledger.change_policy(self.admin[org], grant, expected_revision=policy.revision,
                                             approval_ref=grant.grant_id)

    def close(self):
        # A failed close with live processing must not release shared ownership.
        self.gateway.close()
        self.ledger.close()


def execution_laboratory(root, **kwargs):
    return ExecutionFixture(root, **kwargs)
