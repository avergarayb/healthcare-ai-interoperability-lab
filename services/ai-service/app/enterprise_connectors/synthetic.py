"""In-process doubles only. No tokens, SDK, sockets, URLs fetched or persistence."""
from dataclasses import dataclass, field
from threading import RLock

from .models import ConnectorAccessDecision, ConnectorFailure, Reason


@dataclass(frozen=True, slots=True, repr=False)
class SyntheticCredentialUse:
    decision: ConnectorAccessDecision = field(repr=False)


class SyntheticBroker:
    def __init__(self, ledger):
        self.ledger = ledger
        self.attempts = self.acquisitions = 0
        self.available = True
        self.expired = self.revoked = False
        self._uses: dict[int, SyntheticCredentialUse] = {}
        self.on_acquire = lambda: None

    def acquire(self, decision):
        with self.ledger.store.lock:
            self.ledger.consume(decision)
            self.attempts += 1
            self.on_acquire()
            if not self.available or self.revoked:
                raise ConnectorFailure(Reason.CREDENTIAL, unavailable=True)
            if self.expired:
                raise ConnectorFailure(Reason.CREDENTIAL_EXPIRED)
            use = SyntheticCredentialUse(decision)
            self._uses[id(use)] = use
            self.acquisitions += 1
            return use

    def validate(self, use):
        with self.ledger.store.lock:
            if type(use) is not SyntheticCredentialUse or self._uses.get(id(use)) is not use:
                raise ConnectorFailure(Reason.REPLAY)
            if self.revoked or not self.available:
                raise ConnectorFailure(Reason.CREDENTIAL, unavailable=True)
            if self.expired:
                raise ConnectorFailure(Reason.CREDENTIAL_EXPIRED)
            decision = use.decision
            snapshot = self.ledger.store.snapshot()
            if snapshot.revision != decision.policy_revision or self.ledger.policy.clock() >= decision.expires_at:
                raise ConnectorFailure(Reason.STALE)
            return self.ledger.policy.evaluate(snapshot, decision.context, decision.request)

    def release(self, use):
        with self.ledger.store.lock:
            self._uses.pop(id(use), None)


@dataclass(frozen=True, slots=True)
class SyntheticPage:
    text: str = field(default="", repr=False)
    status: int = 200  # 0 means a simulated timeout, not a transport operation.
    mime: str = "text/plain"
    next_cursor: int | str | None = None
    redirect: str | None = None
    active: bool = False
    compressed: bool = False
    item_ids: tuple[str, ...] = ()


class SyntheticDocumentAdapter:
    def __init__(self, broker, pages, external_permissions):
        self.broker, self._pages = broker, dict(pages)
        self._permissions = set(external_permissions)
        self._lock = RLock()
        self._calls: list[tuple[str, str, str, int]] = []
        self.on_read = lambda resource_id, cursor: None
        self.profile_compatible = True

    @property
    def calls(self):
        with self._lock:
            return tuple(self._calls)

    def set_permission(self, key, enabled):
        with self._lock:
            if enabled:
                self._permissions.add(key)
            else:
                self._permissions.discard(key)

    def set_pages(self, resource_id, pages):
        with self._lock:
            self._pages[resource_id] = tuple(pages)

    def authorize_delivery(self, resources):
        """One consistent simulated permission check; no Graph call or new read."""
        with self._lock:
            if not self.profile_compatible or any(
                    (resource.organization_id, resource.instance_id, resource.resource_id) not in self._permissions
                    for resource in resources):
                raise ConnectorFailure(Reason.EXTERNAL)

    def read(self, use, cursor):
        # Check and register the simulated read atomically with local revocation.
        # Hooks run AFTER that read, outside locks, to model in-flight changes.
        with self.broker.ledger.store.lock:
            evaluation = self.broker.validate(use)
            resource = evaluation.resource
            key = (resource.organization_id, resource.instance_id, resource.resource_id)
            with self._lock:
                self._calls.append((*key, cursor))
                pages = self._pages.get(resource.resource_id)
                if not self.profile_compatible:
                    page = SyntheticPage(status=401)
                elif key not in self._permissions:
                    page = SyntheticPage(status=403)
                elif pages is None or cursor >= len(pages):
                    page = SyntheticPage(status=404)
                else:
                    page = pages[cursor]
        self.on_read(resource.resource_id, cursor)
        return page
