"""Graph wire semantics over explicitly injected OFFLINE ports; no HTTP client."""
from dataclasses import dataclass, field
from threading import RLock
import re

from ...models import ConnectorFailure, ConnectorOperation as Op, Reason
from ...synthetic import SyntheticPage
from .requests import GraphDownloadPolicy, GraphRequestBuilder
from .responses import GraphErrorMapper, GraphResponseParser
from .types import GraphCatalog, GraphCredentialProvider, GraphRequest, GraphResponse, GraphTransport, reject


@dataclass(slots=True, repr=False)
class _Exchange:
    use: object
    calls: int = 0
    wire_bytes: int = 0
    cursor: int = 0
    link: str | None = None
    links: set[str] = field(default_factory=set)
    items: set[str] = field(default_factory=set)


class GraphReadAdapter:
    def __init__(self, store, credentials: GraphCredentialProvider, transport: GraphTransport,
                 catalog: GraphCatalog, *, download=GraphDownloadPolicy(), retry_wait=None):
        if (credentials.offline is not True or transport.offline is not True
                or type(catalog) is not GraphCatalog or type(download) is not GraphDownloadPolicy):
            raise reject()
        self.store, self.credentials, self.transport, self.catalog = store, credentials, transport, catalog
        self.download, self.retry_wait = download, retry_wait
        self.builder, self.parser = GraphRequestBuilder(), GraphResponseParser()
        self._lock, self._exchanges = RLock(), {}

    def release(self, use):
        """Composition's broker.release MUST invoke this, also on failed operations."""
        with self._lock:
            self._exchanges.pop(id(use), None)

    def _exchange(self, use):
        with self._lock:
            if id(use) not in self._exchanges:
                if len(self._exchanges) >= 128:
                    raise reject(Reason.LIMIT)
                self._exchanges[id(use)] = _Exchange(use)
            state = self._exchanges[id(use)]
            if state.use is not use:
                raise reject(Reason.REPLAY)
            return state

    def _send(self, use, state, request, limits, *, download=False):
        # No database transaction or database/Python policy lock held across this port.
        if self.store._current.get() is not None:
            raise reject()
        self.credentials.validate(use)
        if state.calls >= limits.max_attempts:
            raise reject(Reason.LIMIT)
        state.calls += 1
        authorization = None if download else self.credentials.authorization(use, request.resource)
        try:
            response = self.transport.send(request, authorization)
        except TimeoutError:
            response = GraphResponse(408)
        if type(response) is not GraphResponse or type(response.status) is not int or not 200 <= response.status <= 599:
            raise reject()
        if type(response.body) is not bytes:
            raise reject(Reason.CONTENT)
        state.wire_bytes += len(response.body)
        if len(response.body) > min(8192, limits.max_bytes * 8) or state.wire_bytes > min(32768, limits.max_bytes * 16):
            raise reject(Reason.LIMIT)
        response.header("Content-Type")  # Validate every header, including duplicates.
        length = response.header("Content-Length")
        if length is not None and length != str(len(response.body)):
            raise reject(Reason.CONTENT)
        return response

    def _error(self, response, use):
        if response.status == 429:
            delay = response.header("Retry-After")
            if delay is None or not re.fullmatch(r"[0-9]{1,2}", delay):
                raise reject(Reason.PROVIDER)
            seconds = int(delay)
            if seconds >= (use.decision.expires_at - self.store.clock()).total_seconds():
                raise reject(Reason.LIMIT)
            if seconds:
                if self.retry_wait is None:
                    raise reject(Reason.PROVIDER)
                self.retry_wait(seconds)  # Injected virtual clock only in this increment.
        return GraphErrorMapper.page(response.status)

    def _json(self, response, limits):
        if (response.header("Content-Type") not in {"application/json", "application/json; charset=utf-8"}
                or response.header("Content-Encoding") is not None):
            raise reject(Reason.CONTENT)
        return self.parser.load(response.body, min(8192, limits.max_bytes * 8))

    def read(self, use, cursor):
        try:
            evaluation = self.credentials.validate(use)
            snapshot = self.store.snapshot()
            identity = self.catalog.resolve(evaluation.resource, snapshot)
            if ((identity.organization_id, identity.instance_id, identity.tenant_id)
                    != (evaluation.binding.organization_id, evaluation.binding.instance_id, evaluation.binding.tenant_id)):
                raise reject(Reason.BINDING)
            operation, limits = use.decision.request.operation, evaluation.definition.limits
            state = self._exchange(use)
            if type(cursor) is not int or cursor != state.cursor or cursor >= limits.max_pages:
                raise reject(Reason.LIMIT)
            if operation == Op.READ:
                if self.download.enabled is not True or cursor != 0:
                    raise reject(Reason.CONTENT)
                metadata_response = self._send(use, state, self.builder.build(identity, Op.METADATA), limits)
                if metadata_response.status != 200:
                    return self._error(metadata_response, use)
                metadata = self.parser.metadata(self._json(metadata_response, limits), identity, self.store.clock, limits.max_bytes)
                response = self._send(use, state, self.builder.build(identity, operation), limits)
                if response.status == 302:
                    location = self.download.validate(response.header("Location"))
                    response = self._send(use, state, GraphRequest(operation, identity, location, "download"), limits, download=True)
                if response.status != 200:
                    return self._error(response, use)
                text = self.parser.content(response, metadata, limits.max_bytes)
                return SyntheticPage(text=text)
            response = self._send(use, state, self.builder.build(identity, operation, state.link), limits)
            if response.status != 200:
                return self._error(response, use)
            data = self._json(response, limits)
            if operation == Op.METADATA:
                self.parser.metadata(data, identity, self.store.clock, limits.max_bytes)
                return SyntheticPage()
            if operation != Op.CHILDREN or set(data) - {"value", "@odata.nextLink"} or type(data.get("value")) is not list:
                raise reject(Reason.CONTENT)
            items = data["value"]
            if len(items) + len(state.items) > limits.max_items:
                raise reject(Reason.LIMIT)
            children = []
            # Resolve only existing resources; parser never registers or grants children.
            for item in items:
                if type(item) is not dict or type(item.get("id")) is not str or item["id"] in state.items:
                    raise reject(Reason.RESOURCE)
                child = self.catalog.child(item["id"], identity, self.store.snapshot())
                self.parser.metadata(item, child, self.store.clock, limits.max_bytes)
                state.items.add(item["id"])
                children.append(child.resource_id)
            next_cursor = None
            if "@odata.nextLink" in data:
                link = data["@odata.nextLink"]
                canonical = self.builder.continuation(identity, link)
                if canonical in state.links:
                    raise reject()
                state.links.add(canonical)
                state.link, next_cursor = link, cursor + 1
                state.cursor = next_cursor
            return SyntheticPage(item_ids=tuple(children), next_cursor=next_cursor)
        except ConnectorFailure as failure:
            if failure.reason in {Reason.IDENTITY, Reason.EXPIRED, Reason.STALE, Reason.GRANT,
                                  Reason.NOT_REGISTERED, Reason.CREDENTIAL, Reason.CREDENTIAL_EXPIRED, Reason.REPLAY}:
                raise
            return SyntheticPage(status=400)
        except Exception:
            # Fixed public failure: never propagate a transport body, URL or exception.
            return SyntheticPage(status=400)

    def authorize_delivery(self, resources):
        # Pure, in-process simulated external permission check. NEVER Graph I/O.
        try:
            identities = tuple(self.catalog.resolve(r, self.store.snapshot()) for r in resources)
            self.transport.authorize_delivery(identities)
        except ConnectorFailure:
            raise
        except Exception:
            raise ConnectorFailure(Reason.PROVIDER, unavailable=True) from None
