"""TEST ONLY control-plane authority and explicit SQLite opt-in composition."""
from dataclasses import dataclass, replace
from datetime import timedelta

from app.enterprise_connectors.control_plane import ControlPlane
from app.enterprise_connectors.control_types import AdministrativeContext, CredentialMetadata, CredentialState, InstanceState
from app.enterprise_connectors.durable_audit import SQLiteConnectorAudit
from app.enterprise_connectors.models import ConnectorOperation, OperationRequest
from app.enterprise_connectors.policy import DecisionLedger, PolicyEvaluator
from app.enterprise_connectors.service import ConnectorService
from app.enterprise_connectors.sqlite_store import SQLitePolicyStore
from app.enterprise_connectors.synthetic import SyntheticBroker, SyntheticDocumentAdapter
from tests.enterprise_connector_fixture import Clock, TestIdentityFactory, laboratory


class AdministrativeTestAuthority:
    def __init__(self, clock):
        self.clock, self._issued = clock, {}

    def issue(self, suffix="a", role="administrator"):
        actor_type = {"administrator": "synthetic_administrator", "operator": "synthetic_operator", "reader": "workload"}[role]
        context = AdministrativeContext("synthetic-" + role + "-" + suffix, "ORG-" + suffix.upper(), role,
                                        self.clock() + timedelta(hours=1), actor_type)
        self._issued[id(context)] = context
        return context

    def recognizes(self, context):
        return context is not None and self._issued.get(id(context)) is context


@dataclass
class PersistentLaboratory:
    store: SQLitePolicyStore
    control: ControlPlane
    authority: AdministrativeTestAuthority
    clock: Clock
    source: object
    identity: TestIdentityFactory
    admin_a: AdministrativeContext
    admin_b: AdministrativeContext

    @property
    def revision(self):
        return self.store.snapshot().revision

    def invoke(self, method, *args, actor=None, **kwargs):
        return getattr(self.control, method)(self.admin_a if actor is None else actor, *args,
                                            expected_revision=self.revision, **kwargs)

    def onboard(self, suffix="a", *, activate=True):
        actor = self.admin_a if suffix == "a" else self.admin_b
        snapshot = self.source.store.snapshot()
        definition = replace(snapshot.definitions[0], definition_id="definition-" + suffix)
        self.invoke("register", "definitions", definition, actor=actor)
        principal = next(p for p in snapshot.principals if p.principal_id == "principal-" + suffix)
        self.invoke("register", "principals", principal, actor=actor)
        self.invoke("create_instance", "instance-" + suffix, definition.definition_id, actor=actor)
        binding = next(b for b in snapshot.bindings if b.instance_id == "instance-" + suffix)
        self.invoke("register", "bindings", binding, actor=actor)
        for resource in snapshot.resources:
            if resource.instance_id == binding.instance_id:
                self.invoke("register", "resources", resource, actor=actor)
        for kind in ("external_grants", "principal_grants"):
            grant = next(g for g in getattr(snapshot, kind) if g.instance_id == binding.instance_id)
            self.invoke("register", kind, grant, actor=actor)
        reference = next(c for c in snapshot.credentials if c.instance_id == binding.instance_id)
        self.invoke("register_credential", CredentialMetadata(reference, binding.binding_id,
                    "synthetic-custody." + suffix, self.clock() + timedelta(minutes=30)), actor=actor)
        if activate:
            self.invoke("transition_credential", reference.reference_id, CredentialState.ACTIVE, actor=actor)
            for operation in ("submit", "approve", "activate"):
                self.invoke("transition", binding.instance_id, operation, actor=actor)

    def reader(self, *, store=None, cache_size=0):
        store = self.store if store is None else store
        policy = PolicyEvaluator(self.identity, self.clock)
        ledger = DecisionLedger(store, policy)
        broker = SyntheticBroker(ledger)
        adapter = SyntheticDocumentAdapter(broker, self.source.adapter._pages,
                                            self.source.adapter._permissions)
        audit = SQLiteConnectorAudit(store)
        service = ConnectorService(store, policy, audit, ledger, broker, adapter, cache_size=cache_size)
        return service, broker, adapter, audit

    def request(self, suffix="a", resource_id=None):
        return OperationRequest("instance-" + suffix, resource_id or "vacation-" + suffix,
                                ConnectorOperation.READ, "synthetic-demonstration", "recipient-" + suffix, self.revision)

    def context(self, suffix="a"):
        return self.identity.issue("principal-" + suffix)

    def peer(self):
        return SQLitePolicyStore(self.store.path, test_owned_root=self.store.root, clock=self.clock)


def persistent_laboratory(tmp_path, *, onboard=True):
    clock, source = Clock(), laboratory()
    authority = AdministrativeTestAuthority(clock)
    store = SQLitePolicyStore(tmp_path / "connectors.sqlite3", test_owned_root=tmp_path, clock=clock)
    control = ControlPlane(store, authority)
    admin_a, admin_b = authority.issue(), authority.issue("b")
    control.initialize(admin_a)
    identity = TestIdentityFactory(source.store.snapshot().principals, clock)
    lab = PersistentLaboratory(store, control, authority, clock, source, identity, admin_a, admin_b)
    if onboard:
        lab.onboard()
    return lab
