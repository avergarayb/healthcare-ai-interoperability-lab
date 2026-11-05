"""TEST ONLY Graph transport/authorization, synthetic payloads and SQLite composition."""
from dataclasses import dataclass, replace
import json
from threading import RLock

from app.enterprise_connectors.durable_audit import SQLiteConnectorAudit
from app.enterprise_connectors.models import ConnectorFailure, ConnectorOperation as Op, Reason
from app.enterprise_connectors.policy import DecisionLedger, PolicyEvaluator
from app.enterprise_connectors.providers.microsoft_graph.adapter import GraphReadAdapter
from app.enterprise_connectors.providers.microsoft_graph.requests import GraphDownloadPolicy, GraphRequestBuilder
from app.enterprise_connectors.providers.microsoft_graph.types import GraphCatalog, GraphRequest, GraphResourceIdentity, GraphResponse
from app.enterprise_connectors.service import ConnectorService
from app.enterprise_connectors.synthetic import SyntheticBroker
from tests.enterprise_connector_control_plane_fixture import persistent_laboratory


@dataclass(frozen=True, slots=True, repr=False)
class OfflineTransportAuthority:
    """Has no bearer/header/string representation usable at Microsoft."""
    use: object
    scope: tuple[str, ...]


class TestGraphCredentials(SyntheticBroker):
    __test__ = False
    offline = True

    def __init__(self, ledger):
        super().__init__(ledger)
        self._authorities, self.adapter = {}, None

    def authorization(self, use, identity):
        evaluation = self.validate(use)
        scope = (identity.organization_id, identity.instance_id, identity.tenant_id)
        if scope != (evaluation.credential.organization_id, evaluation.credential.instance_id, evaluation.credential.tenant_id):
            raise ConnectorFailure(Reason.CREDENTIAL)
        authority = OfflineTransportAuthority(use, (*scope, evaluation.credential.reference_id))
        self._authorities[id(authority)] = authority
        return authority

    def recognizes(self, authority, identity):
        if type(authority) is not OfflineTransportAuthority or self._authorities.get(id(authority)) is not authority:
            return False
        self.validate(authority.use)
        return authority.scope[:3] == (identity.organization_id, identity.instance_id, identity.tenant_id)

    def release(self, use):
        if self.adapter is not None:
            self.adapter.release(use)
        self._authorities = {key: value for key, value in self._authorities.items() if value.use is not use}
        super().release(use)


def json_response(data, *, status=200, headers=()):
    return GraphResponse(status, json.dumps(data, separators=(",", ":")).encode("utf-8"),
                         (("Content-Type", "application/json"), *headers))


class OfflineGraphTransport:
    offline = True

    def __init__(self, store, credentials, catalog, texts):
        self.store, self.credentials, self.catalog, self.texts = store, credentials, catalog, texts
        self._lock, self._calls, self._counts = RLock(), [], {}
        self.responses, self.after_send = {}, lambda request, response: None
        self.permissions = {(i.organization_id, i.instance_id, i.resource_id) for i in catalog.identities
                            if not i.resource_id.startswith("outside-")}
        self.delivery_checks = 0

    @property
    def calls(self):
        with self._lock:
            return tuple(self._calls)

    def set_permission(self, resource_id, enabled, *, suffix="a"):
        key = ("ORG-" + suffix.upper(), "instance-" + suffix, resource_id)
        with self._lock:
            self.permissions.add(key) if enabled else self.permissions.discard(key)

    def identity(self, resource_id):
        return next(i for i in self.catalog.identities if i.resource_id == resource_id)

    def metadata(self, identity):
        parent = {"driveId": identity.drive_id, "driveType": identity.drive_type}
        if identity.parent_item_id is not None:
            parent["id"] = identity.parent_item_id
        if identity.site_id is not None:
            parent["siteId"] = identity.site_id
        data = {"id": identity.item_id, "eTag": identity.e_tag, "parentReference": parent,
                "size": len(self.texts.get(identity.resource_id, "").encode("utf-8")), "name": "Ignored synthetic title"}
        if identity.resource_type == "folder":
            data["folder"] = {"childCount": 3}
        else:
            data["file"] = {"mimeType": "text/plain"}
        return data

    def content(self, identity):
        body = self.texts.get(identity.resource_id, "").encode("utf-8")
        return GraphResponse(200, body, (("Content-Type", "text/plain"), ("Content-Length", str(len(body))),
                                         ("ETag", identity.e_tag)))

    def queue(self, operation, responses, *, resource_id="vacation-a", purpose="graph"):
        self.responses[(resource_id, operation, purpose)] = tuple(responses)

    def send(self, request, authorization):
        assert self.store._current.get() is None, "Wire port inside SQLite transaction"
        assert type(request) is GraphRequest and request.method == "GET"
        if request.purpose == "download":
            assert authorization is None, "Graph authority must never reach download"
            GraphDownloadPolicy(True, frozenset({"download-a.invalid", "download-b.invalid"})).validate(request.target)
        else:
            assert request.purpose == "graph" and self.credentials.recognizes(authorization, request.resource)
            builder = GraphRequestBuilder()
            if "$skiptoken" in request.target:
                builder.continuation(request.resource, request.target)
            else:
                assert request.target == builder.build(request.resource, request.operation).target
        i = request.resource
        key = (i.organization_id, i.instance_id, i.resource_id)
        route = (i.resource_id, request.operation, request.purpose)
        with self._lock:
            self._calls.append((request.method, request.operation.value, *key, request.purpose, authorization is not None))
            count = self._counts.get(route, 0)
            self._counts[route] = count + 1
            queued = self.responses.get(route)
            if key not in self.permissions:
                response = GraphResponse(403)
            elif queued:
                response = queued[min(count, len(queued) - 1)]
            elif request.purpose == "download" or request.operation == Op.READ:
                response = self.content(i)
            elif request.operation == Op.METADATA:
                response = json_response(self.metadata(i))
            else:
                children = [self.metadata(c) for c in self.catalog.identities
                            if (c.organization_id, c.instance_id, c.parent_item_id)
                            == (i.organization_id, i.instance_id, i.item_id)]
                response = json_response({"value": children})
        if isinstance(response, Exception):
            raise response
        self.after_send(request, response)
        return response

    def authorize_delivery(self, identities):
        with self._lock:
            self.delivery_checks += 1
            if any((i.organization_id, i.instance_id, i.resource_id) not in self.permissions for i in identities):
                raise ConnectorFailure(Reason.EXTERNAL)


@dataclass
class GraphLaboratory:
    persistent: object
    credentials: TestGraphCredentials
    transport: OfflineGraphTransport
    catalog: GraphCatalog
    adapter: GraphReadAdapter
    audit: SQLiteConnectorAudit
    service: ConnectorService

    def request(self, *, suffix="a", resource=None, operation=Op.READ):
        return replace(self.persistent.request(suffix, resource), operation=operation)

    def execute(self, *, suffix="a", resource=None, operation=Op.READ, request=None, context=None, **kwargs):
        result = self.service.execute(self.persistent.context(suffix) if context is None else context,
                                      self.request(suffix=suffix, resource=resource, operation=operation) if request is None else request, **kwargs)
        assert not self.adapter._exchanges and not self.credentials._authorities
        return result


def graph_laboratory(tmp_path, *, shared_tenant=False, both=False, cache_size=0, download=True):
    lab = persistent_laboratory(tmp_path, onboard=False)
    if shared_tenant:
        for table in ("bindings", "resources", "credentials"):
            snapshot = lab.source.store.snapshot()
            rows = tuple(replace(row, tenant_id="shared-tenant") for row in getattr(snapshot, table))
            lab.source.store.replace_rows(table, rows, expected_revision=snapshot.revision)
    lab.onboard()
    if both:
        lab.onboard("b")
    snapshot = lab.store.snapshot()
    identities = []
    for resource in snapshot.resources:
        suffix = resource.instance_id[-1]
        parent = next((r for r in snapshot.resources if r.resource_id == resource.parent_id), None)
        identities.append(GraphResourceIdentity(resource.organization_id, resource.instance_id, resource.resource_id,
            resource.tenant_id, "b!synthetic-drive-" + ("shared" if shared_tenant else suffix), resource.external_id,
            None if parent is None else parent.external_id, resource.resource_type, resource.version, '"synthetic-v1"',
            "fixture.invalid,site-" + ("shared" if shared_tenant else suffix) + ",web-fixture"))
    catalog = GraphCatalog(tuple(identities))
    policy = PolicyEvaluator(lab.identity, lab.clock)
    ledger = DecisionLedger(lab.store, policy)
    credentials = TestGraphCredentials(ledger)
    texts = {r.resource_id: lab.source.adapter._pages[r.resource_id][0].text for r in snapshot.resources
             if r.resource_id in lab.source.adapter._pages and r.resource_type == "document"}
    transport = OfflineGraphTransport(lab.store, credentials, catalog, texts)
    downloads = GraphDownloadPolicy(download, frozenset({"download-a.invalid", "download-b.invalid"}))
    adapter = GraphReadAdapter(lab.store, credentials, transport, catalog, download=downloads, retry_wait=lab.clock.advance)
    credentials.adapter = adapter
    audit = SQLiteConnectorAudit(lab.store)
    service = ConnectorService(lab.store, policy, audit, ledger, credentials, adapter, cache_size=cache_size)
    return GraphLaboratory(lab, credentials, transport, catalog, adapter, audit, service)
