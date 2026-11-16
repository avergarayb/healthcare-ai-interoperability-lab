"""Use-case agent. It calls only the operational gateway and does not build a grant."""
from app.enterprise_llm_providers.errors import ProviderError

from .gateway import NeutralModelGateway


class VacationClauseAgent:
    def __init__(self, gateway):
        if type(gateway) is not NeutralModelGateway:
            raise ProviderError("remote_not_authorized")
        self._gateway = gateway

    def run(self, access, authorization_id, budget_microusd, resource_id, deployment_id,
            supplied_url=None, operation_id="vacation-days-v1"):
        return self._gateway.execute(
            access, authorization_id, budget_microusd, resource_id, deployment_id,
            supplied_url, operation_id)
