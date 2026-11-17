"""SQLite adapter for the neutral authorization port. Only the real ledger class is accepted."""
from datetime import timedelta

from app.enterprise_llm_providers.errors import ProviderError
from app.model_gateway.authorization import DurableAuthorizationResolver, DurableDecision

from .remote_authorization import RemoteAuthorization
from .sqlite_ledger import SQLiteExecutionLedger


class LedgerDurableAuthorization(DurableAuthorizationResolver):
    """Reads one enterprise ledger. A substitute object is not an authority."""

    def __init__(self, ledger):
        if type(ledger) is not SQLiteExecutionLedger:
            raise ProviderError("remote_not_authorized")
        self._ledger = ledger

    def resolve(self, access, authorization_id, deployment, resource_id, budget_microusd):
        if access is None:
            return DurableDecision(False, "authority_unverifiable", None, None, None, None, None)
        try:
            organization_id = access.organization_id
            principal_id = access.principal_id
            now = self._ledger.clock()
            record = RemoteAuthorization(
                authorization_id, organization_id, deployment.deployment_id,
                deployment.identity.provider_id, deployment.identity.model_id,
                now, now + timedelta(minutes=1), principal_id=principal_id, resource_id=resource_id)
        except Exception:
            return DurableDecision(False, "invalid_input", None, None, None, None, None)
        decision = self._ledger.evaluate_remote_authorization(
            access, record, requested_budget_microusd=budget_microusd)
        allowed = decision.allowed is True and decision.reason == "accepted"
        return DurableDecision(
            allowed, decision.reason, decision.authorization_id,
            deployment.deployment_id if allowed else None,
            deployment.identity.provider_id if allowed else None,
            deployment.identity.model_id if allowed else None,
            organization_id if allowed else None)

    def clock(self):
        return self._ledger.clock

    def confirm_hold(self, access, authorization_id, deployment, resource_id, budget_microusd):
        """The hold must still be the committed row. A memory grant is not enough."""
        try:
            return self._ledger.read_operational_hold(
                access, authorization_id, deployment.deployment_id, deployment.identity.provider_id,
                deployment.identity.model_id, resource_id, budget_microusd)
        except Exception:
            return "storage_unavailable"

    def consume(self, access, authorization_id):
        try:
            self._ledger.consume_remote_reservation(access, authorization_id)
        except Exception:
            raise ProviderError("storage_unavailable") from None
