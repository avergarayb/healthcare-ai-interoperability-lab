"""Neutral model gateway. It selects one authorized deployment and does not fall back."""
import threading

from app.enterprise_llm_providers.errors import ProviderError
from app.enterprise_llm_providers.schema import QUESTION_ID
from app.enterprise_llm_providers.smoke import FIXED_DOCUMENT
from app.enterprise_llm_providers.validation import check_observation

from .adapters import lab_adapters
from .contracts import ExecutionPolicy, GatewayResult, ModelRequest
from .policy import authorize, default_policy
from .registry import ProviderRegistry, reject_caller_destination


class NeutralModelGateway:
    def __init__(self, registry=None, adapters=None, policy=None):
        self._registry = registry if registry is not None else ProviderRegistry()
        self._adapters = lab_adapters() if adapters is None else adapters
        self._policy = default_policy() if policy is None else policy
        if type(self._policy) is not ExecutionPolicy:
            raise ProviderError("policy_denied")
        self._lock = threading.Lock()
        self._spent = set()
        self._inflight = set()

    def __repr__(self):
        return "NeutralModelGateway(closed)"

    def execute(self, context, grant, supplied_url=None):
        reject_caller_destination(supplied_url)
        deployment = self._registry.get(grant.deployment_id if grant is not None else None)
        with self._lock:
            if deployment.deployment_id in self._spent or deployment.deployment_id in self._inflight:
                raise ProviderError("replay_denied")
            authorize(context, grant, deployment)
            adapter = self._adapters.get(deployment.deployment_id)
            if adapter is None:
                raise ProviderError("model_unregistered")
            request = ModelRequest(
                QUESTION_ID, context.organization_id, context.principal_id, context.resource_id, FIXED_DOCUMENT)
            reservation = adapter.estimate_cost(request, deployment)
            if reservation != deployment.reservation_microusd or context.budget_microusd < reservation:
                raise ProviderError("budget_exceeded")
            self._inflight.add(deployment.deployment_id)
        try:
            response = adapter.invoke_once(request, deployment)
        except ProviderError as error:
            with self._lock:
                self._inflight.discard(deployment.deployment_id)
                self._spent.add(deployment.deployment_id)
            raise ProviderError(error.reason, getattr(error, "diagnostic", None)) from None
        with self._lock:
            self._inflight.discard(deployment.deployment_id)
            self._spent.add(deployment.deployment_id)
        if response.usage.input_tokens is None or response.usage.output_tokens is None:
            raise ProviderError("consumption_ambiguous")
        check_observation(FIXED_DOCUMENT.encode("utf-8"), response.observation)
        return GatewayResult(
            True, "accepted", deployment.deployment_id, context.organization_id,
            response.usage.input_tokens, response.usage.output_tokens, reservation,
            response.estimated_microusd, response.thoughts_tokens, response.cost_exact,
            response.thoughts_inferred, response.tool_inferred,
            response.prompt_inferred, response.visible_inferred)

    def public_state(self, result, organization_id):
        if type(result) is not GatewayResult or result.organization_id != organization_id:
            raise ProviderError("remote_not_authorized")
        return {
            "phase": "completed" if result.accepted else "denied",
            "reason": result.reason,
            "organization_id": result.organization_id,
            "deployment_id": result.deployment_id,
        }
