"""Authorized synthetic operations, ready for explicit internal consumers only."""
from dataclasses import replace
from datetime import timedelta
from typing import Protocol
from uuid import uuid4

from .audit import AuditSink
from .models import (
    ConnectorAccessDecision, ConnectorAuditEvent, ConnectorExecutionContext, ConnectorFailure, ConnectorOperation,
    Gate, OperationRequest, OperationResult, Outcome, Phase, Reason, UntrustedDocument,
)
from .policy import DecisionLedger, PolicyEvaluator


class CredentialBroker(Protocol):
    def acquire(self, decision: ConnectorAccessDecision): ...
    def release(self, use) -> None: ...


class DocumentAdapter(Protocol):
    def read(self, use, cursor: int): ...
    def authorize_delivery(self, resources) -> None: ...


class ConnectorService:
    def __init__(self, store, policy: PolicyEvaluator, audit: AuditSink, ledger: DecisionLedger,
                 broker: CredentialBroker, adapter: DocumentAdapter, *, cache_size=0):
        if type(cache_size) is not int or not 0 <= cache_size <= 8:
            raise ValueError("laboratory cache limit is 0..8")
        self.store, self.policy, self.audit = store, policy, audit
        self.ledger, self.broker, self.adapter = ledger, broker, adapter
        self.cache_size, self._cache = cache_size, {}
        self._active = {}
        self._cache_revision = store.snapshot().revision

    def _event(self, context, request, correlation, phase, outcome, reason):
        snapshot = self.store.snapshot()
        # Resolve attribution only from boundary and registered same-org records.
        trusted = type(context) is ConnectorExecutionContext and self.policy.identity.recognizes(context)
        principal = next((p for p in snapshot.principals if trusted and p.enabled
                          and p.principal_id == context.principal_id and p.organization_id == context.organization_id), None)
        instance = next((i for i in snapshot.instances if principal and type(request) is OperationRequest
                         and i.instance_id == request.instance_id and i.organization_id == principal.organization_id), None)
        resource = next((r for r in snapshot.resources if instance and r.resource_id == request.resource_id
                         and r.organization_id == principal.organization_id and r.instance_id == instance.instance_id), None)
        event = ConnectorAuditEvent(
            str(uuid4()), correlation, self.policy.clock(), phase, outcome, reason, snapshot.revision,
            None if principal is None else principal.principal_id,
            None if principal is None else principal.organization_id,
            None if instance is None else instance.instance_id,
            None if resource is None else resource.resource_id,
            request.operation if type(request) is OperationRequest and type(request.operation) is ConnectorOperation else None,
        )
        try:
            self.audit.append(event)
        except Exception:
            raise ConnectorFailure(Reason.AUDIT, unavailable=True) from None

    def _validate_delivery(self, context, request, documents, local_only):
        snapshot = self.store.snapshot()
        delivery = self.policy.evaluate(snapshot, context, request, Gate.DELIVERY)
        resources = [delivery.resource]
        for document in documents:
            if document.resource_id == delivery.resource.resource_id:
                continue
            item = self.policy.evaluate(snapshot, context, replace(
                request, resource_id=document.resource_id,
                operation=ConnectorOperation.METADATA), Gate.DELIVERY)
            resources.append(item.resource)
        if not local_only:
            self.adapter.authorize_delivery(tuple(resources))

    def execute(self, context, request, *, gate=Gate.READ):
        correlation = str(uuid4())
        local, external = Outcome.DENY, None
        observed_external = [None]
        use = None
        active_key = None
        try:
            with self.store.lock:
                snapshot = self.store.snapshot()
                if self._cache_revision != snapshot.revision:
                    self._cache.clear()
                    self._cache_revision = snapshot.revision
                evaluation = self.policy.evaluate(snapshot, context, request, gate)
                # C and D can never reach this point; gate B cannot acquire data alone.
                if gate != Gate.READ:
                    raise ConnectorFailure(Reason.DATA_USE)
                candidate_key = (context.organization_id, request.instance_id)
                if self._active.get(candidate_key, 0) >= evaluation.definition.limits.max_concurrent:
                    raise ConnectorFailure(Reason.LIMIT)
                self._event(context, request, correlation, Phase.AUTHORIZATION, Outcome.LOCAL_ALLOW, Reason.ALLOWED)
                self.policy.evaluate(self.store.snapshot(), context, request)
                local = Outcome.LOCAL_ALLOW
                active_key = candidate_key
                self._active[active_key] = self._active.get(active_key, 0) + 1
                deadline = self.policy.clock() + timedelta(seconds=evaluation.definition.limits.max_seconds)
                key = (context.principal_id, context.organization_id, request, evaluation.resource, snapshot.revision)
                cached = self._cache.get(key)
                documents = None if cached is None else cached[1]
                if cached is not None and self.policy.clock() >= cached[0]:
                    self._cache.pop(key)
                    documents = None
                local_only = request.operation in {ConnectorOperation.RESOLVE, ConnectorOperation.PROVENANCE}
                if documents is None and not local_only:
                    decision = ConnectorAccessDecision(str(uuid4()), correlation, context, request,
                                                       snapshot.revision, min(deadline, evaluation.expires_at), Gate.READ)
                    self.ledger.issue(decision)
                    use = self.broker.acquire(decision)
            if documents is None:
                if local_only:
                    resource = evaluation.resource
                    documents = (UntrustedDocument(resource.resource_id, resource.organization_id,
                                                   resource.instance_id, resource.version, ""),)
                else:
                    documents, external = self._read(context, request, correlation, use, deadline, observed_external)
            else:
                # This is cached data, not a new external execution or cached ALLOW.
                external = None
            with self.store.lock:
                if self.policy.clock() >= deadline:
                    raise ConnectorFailure(Reason.LIMIT)
                self._validate_delivery(context, request, documents, local_only)
                self._event(context, request, correlation, Phase.DELIVERY, Outcome.DELIVERY_ALLOWED, Reason.ALLOWED)
                self._validate_delivery(context, request, documents, local_only)
                if self.policy.clock() >= deadline:
                    raise ConnectorFailure(Reason.LIMIT)
                if self.cache_size:
                    self._cache[key] = (min(deadline, evaluation.expires_at), documents)
                    while len(self._cache) > self.cache_size:
                        self._cache.pop(next(iter(self._cache)))
                return OperationResult(Outcome.DELIVERY_ALLOWED, Reason.ALLOWED, correlation,
                                       local, external, Outcome.DELIVERY_ALLOWED, documents)
        except ConnectorFailure as error:
            external = observed_external[0] if observed_external[0] is not None else external
            status = Outcome.UNAVAILABLE if error.unavailable else (
                Outcome.DENY if local == Outcome.DENY else Outcome.DELIVERY_SUPPRESSED)
            if error.reason in {Reason.EXTERNAL, Reason.MISSING}:
                status = external = Outcome.EXTERNAL_DENIED
            phase = Phase.AUTHORIZATION if local == Outcome.DENY else Phase.DELIVERY
            try:
                self._event(context, request, correlation, phase, status, error.reason)
            except ConnectorFailure:
                status, error = Outcome.UNAVAILABLE, ConnectorFailure(Reason.AUDIT, unavailable=True)
            return OperationResult(status, error.reason, correlation, local, external,
                                   None if local == Outcome.DENY else Outcome.DELIVERY_SUPPRESSED)
        finally:
            if use is not None:
                self.broker.release(use)
            if active_key is not None:
                with self.store.lock:
                    self._active[active_key] -= 1
                    if self._active[active_key] == 0:
                        del self._active[active_key]

    def _read(self, context, request, correlation, use, deadline, observed_external):
        cursor = attempts = total_bytes = item_count = 0
        texts: list[str] = []
        resources = {}
        while True:
            with self.store.lock:
                evaluation = self.policy.evaluate(self.store.snapshot(), context, request)
                limits = evaluation.definition.limits
                if cursor >= limits.max_pages or attempts >= limits.max_attempts or self.policy.clock() >= deadline:
                    raise ConnectorFailure(Reason.LIMIT)
            page = self.adapter.read(use, cursor)
            attempts += 1
            success = page.status == 200
            reason = Reason.ALLOWED if success else (
                Reason.EXTERNAL if page.status in {401, 403} else
                Reason.MISSING if page.status == 404 else Reason.PROVIDER)
            outcome = Outcome.EXTERNAL_SUCCESS if success else (
                Outcome.EXTERNAL_DENIED if page.status in {401, 403, 404} else Outcome.UNAVAILABLE)
            observed_external[0] = outcome
            self._event(context, request, correlation, Phase.EXTERNAL, outcome, reason)
            with self.store.lock:
                self.policy.evaluate(self.store.snapshot(), context, request)
                if self.policy.clock() >= deadline:
                    raise ConnectorFailure(Reason.LIMIT)
                if not success:
                    if (page.status == 429 or page.status == 0 or 500 <= page.status < 600) and attempts < limits.max_attempts:
                        continue  # Synthetic bounded retries; no sleep or credential/mode fallback.
                    raise ConnectorFailure(reason, unavailable=outcome == Outcome.UNAVAILABLE)
                if page.redirect is not None or (page.next_cursor is not None
                                                and (type(page.next_cursor) is not int or page.next_cursor != cursor + 1)):
                    raise ConnectorFailure(Reason.TRANSPORT)
                if page.mime not in evaluation.definition.allowed_mimes or page.active or page.compressed:
                    raise ConnectorFailure(Reason.CONTENT)
                total_bytes += len(page.text.encode("utf-8"))
                item_count += len(page.item_ids) if page.item_ids else 1
                if total_bytes > limits.max_bytes or item_count > limits.max_items:
                    raise ConnectorFailure(Reason.LIMIT)
                for resource_id in page.item_ids:
                    child = self.policy.evaluate(self.store.snapshot(), context, replace(
                        request, resource_id=resource_id, operation=ConnectorOperation.METADATA)).resource
                    if child.parent_id != evaluation.resource.resource_id:
                        raise ConnectorFailure(Reason.RESOURCE)
                    resources[child.resource_id] = child
                if request.operation == ConnectorOperation.READ:
                    texts.append(page.text)
                if page.next_cursor is None:
                    break
                cursor = page.next_cursor
        if request.operation == ConnectorOperation.CHILDREN:
            documents = tuple(UntrustedDocument(r.resource_id, r.organization_id, r.instance_id, r.version, "")
                              for r in resources.values())
        else:
            r = evaluation.resource
            documents = (UntrustedDocument(r.resource_id, r.organization_id, r.instance_id, r.version, "".join(texts)),)
        return documents, Outcome.EXTERNAL_SUCCESS
