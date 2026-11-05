"""Deterministic local policy. External simulated authority is a separate check."""
from dataclasses import dataclass
from datetime import datetime

from .models import (
    ConnectorAccessDecision, ConnectorDefinition, ConnectorExecutionContext, ConnectorFailure, ConnectorOperation,
    CredentialReference, Gate, IdentityBoundary, OperationRequest, QualifiedExternalResource,
    Reason, TenantConnectorBinding,
)
from .registry import PolicySnapshot, unique


@dataclass(frozen=True, slots=True)
class Evaluation:
    definition: ConnectorDefinition
    binding: TenantConnectorBinding
    resource: QualifiedExternalResource
    credential: CredentialReference
    expires_at: datetime


def in_scope(snapshot, resource, scope_id, scope):
    if scope not in {"exact", "subtree"}:
        return False
    if scope == "exact" and resource.resource_id != scope_id:
        return False
    current, visited = resource, set()
    matched = False
    for _ in range(16):
        if current.resource_id in visited:
            return False
        visited.add(current.resource_id)
        if current.resource_id == scope_id:
            matched = True
        # Scope membership never hides an invalid/cyclic registered ancestry.
        if current.parent_id is None:
            return matched
        try:
            parent = unique(snapshot.resources, "resource_id", current.parent_id)
        except ConnectorFailure:
            return False
        if (not parent.enabled or parent.kind != "registered" or parent.resource_type != "folder"
                or (parent.organization_id, parent.instance_id, parent.tenant_id, parent.provider, parent.cloud)
                != (resource.organization_id, resource.instance_id, resource.tenant_id, resource.provider, resource.cloud)):
            return False
        current = parent
    return False


class PolicyEvaluator:
    def __init__(self, identity: IdentityBoundary, clock):
        self.identity, self.clock = identity, clock

    def evaluate(self, snapshot: PolicySnapshot, context, request, gate=Gate.READ) -> Evaluation:
        try:
            return self._evaluate(snapshot, context, request, gate)
        except (TypeError, ValueError, AttributeError, OverflowError):
            raise ConnectorFailure(Reason.POLICY, unavailable=True) from None

    def _evaluate(self, s, c, r, gate):
        now = self.clock()
        if type(c) is not ConnectorExecutionContext or not self.identity.recognizes(c):
            raise ConnectorFailure(Reason.IDENTITY)
        if c.principal_type != "workload":
            raise ConnectorFailure(Reason.PRINCIPAL_TYPE)
        if (c.context_version != "identity-principal-context-v1" or c.audience != "healthcare-ai-api"
                or c.authenticated_at > now or now >= c.expires_at):
            raise ConnectorFailure(Reason.EXPIRED)
        principal = unique(s.principals, "principal_id", c.principal_id)
        if not principal.enabled or principal.principal_type != c.principal_type:
            raise ConnectorFailure(Reason.IDENTITY)
        if principal.organization_id != c.organization_id:
            raise ConnectorFailure(Reason.ORGANIZATION)
        if type(r) is not OperationRequest or type(r.operation) is not ConnectorOperation:
            raise ConnectorFailure(Reason.OPERATION)
        if type(gate) is not Gate or gate in {Gate.AI_PROCESS, Gate.INDEX}:
            raise ConnectorFailure(Reason.DATA_USE)
        if type(r.policy_version) is not int or r.policy_version != s.revision:
            raise ConnectorFailure(Reason.STALE)
        instance = unique(s.instances, "instance_id", r.instance_id)
        if instance.organization_id != c.organization_id:
            raise ConnectorFailure(Reason.ORGANIZATION)
        if not instance.enabled or instance.lifecycle_status != "active":
            raise ConnectorFailure(Reason.NOT_REGISTERED)
        definition = unique(s.definitions, "definition_id", instance.definition_id)
        if not definition.enabled:
            raise ConnectorFailure(Reason.NOT_REGISTERED)
        if (r.operation not in definition.operations
                or r.operation in {ConnectorOperation.AI_PROCESS, ConnectorOperation.INDEX, ConnectorOperation.SHARE}):
            raise ConnectorFailure(Reason.OPERATION)
        resource = unique(s.resources, "resource_id", r.resource_id)
        if (not resource.enabled or resource.kind != "registered"
                or resource.organization_id != c.organization_id or resource.instance_id != instance.instance_id):
            raise ConnectorFailure(Reason.RESOURCE)
        if ((r.operation == ConnectorOperation.READ and resource.resource_type != "document")
                or (r.operation == ConnectorOperation.CHILDREN and resource.resource_type != "folder")):
            raise ConnectorFailure(Reason.OPERATION)
        binding = unique(s.bindings, "binding_id", instance.binding_id)
        if (not binding.enabled
                or (binding.organization_id, binding.instance_id, binding.tenant_id, binding.provider, binding.cloud)
                != (c.organization_id, instance.instance_id, resource.tenant_id, resource.provider, resource.cloud)):
            raise ConnectorFailure(Reason.BINDING)
        # Human identity binding is TASK 006, not fabricated from a workload context.
        if instance.mode != "application" or binding.mode != instance.mode:
            raise ConnectorFailure(Reason.MODE)
        credential = unique(s.credentials, "reference_id", instance.credential_ref)
        if (not credential.enabled
                or (credential.organization_id, credential.instance_id, credential.tenant_id, credential.client_id,
                    credential.service_principal_id, credential.provider, credential.cloud, credential.mode)
                != (c.organization_id, instance.instance_id, binding.tenant_id, binding.client_id,
                    binding.service_principal_id, binding.provider, binding.cloud, instance.mode)):
            raise ConnectorFailure(Reason.CREDENTIAL)
        if now >= credential.expires_at:
            raise ConnectorFailure(Reason.CREDENTIAL_EXPIRED)
        def base(grant):
            return (grant.enabled and now < grant.expires_at and type(grant.version) is int and grant.version > 0
                    and grant.organization_id == c.organization_id and grant.instance_id == instance.instance_id
                    and grant.mode == instance.mode and r.operation in grant.operations
                    and in_scope(s, resource, grant.resource_id, grant.scope))
        principal_grants = [g for g in s.principal_grants if base(g) and g.principal_id == c.principal_id
                            and gate in g.gates and r.purpose in g.purposes and r.recipient_id in g.recipients
                            and resource.classification in g.classifications]
        external_grants = [g for g in s.external_grants if base(g) and g.profile == credential.profile]
        # One complete grant per layer; never assemble authority from partial grants.
        if not principal_grants or not external_grants:
            raise ConnectorFailure(Reason.GRANT if gate == Gate.READ else Reason.DATA_USE)
        limits = definition.limits
        if any(type(n) is not int or not 1 <= n <= 1_000_000 for n in (
                limits.max_pages, limits.max_items, limits.max_bytes, limits.max_attempts,
                limits.max_seconds, limits.max_concurrent)):
            raise ConnectorFailure(Reason.LIMIT, unavailable=True)
        if any(type(row.version) is not int or row.version < 1 for row in (instance, definition, resource, binding, credential)):
            raise ConnectorFailure(Reason.POLICY, unavailable=True)
        expiry = min(c.expires_at, credential.expires_at,
                     max(g.expires_at for g in principal_grants), max(g.expires_at for g in external_grants))
        return Evaluation(definition, binding, resource, credential, expiry)


class DecisionLedger:
    """Single-use internal decisions; object identity is not a process/host sandbox."""
    def __init__(self, store, policy):
        self.store, self.policy = store, policy
        self._issued: dict[int, ConnectorAccessDecision] = {}

    def issue(self, decision):
        with self.store.lock:
            self._issued[id(decision)] = decision

    def consume(self, decision):
        with self.store.lock:
            if type(decision) is not ConnectorAccessDecision or self._issued.get(id(decision)) is not decision:
                raise ConnectorFailure(Reason.REPLAY)
            del self._issued[id(decision)]
            snapshot = self.store.snapshot()
            if snapshot.revision != decision.policy_revision or self.policy.clock() >= decision.expires_at:
                raise ConnectorFailure(Reason.STALE)
            return self.policy.evaluate(snapshot, decision.context, decision.request, decision.gate)
