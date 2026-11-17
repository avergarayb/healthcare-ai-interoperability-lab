"""Operational model gateway. Authorization comes from the durable resolver, not a caller grant."""
import threading

from app.enterprise_llm_providers.errors import ProviderError
from app.enterprise_llm_providers.permit import CLASSIFICATION, PURPOSE
from app.enterprise_llm_providers.schema import QUESTION_ID
from app.enterprise_llm_providers.smoke import FIXED_DOCUMENT
from app.enterprise_llm_providers.validation import check_observation

from app.enterprise_ai_processing.durable_resolver import LedgerDurableAuthorization

from .adapters import lab_adapters
from .authorization import DurableAuthorizationResolver
from .contracts import ExecutionContext, ExecutionGrant, ExecutionPolicy, GatewayResult, ModelRequest
from .policy import REQUIRED, authorize, default_policy
from .registry import ProviderRegistry, reject_caller_destination


class NeutralModelGateway:
    def __init__(self, registry=None, adapters=None, policy=None, resolver=None):
        self._registry = registry if registry is not None else ProviderRegistry()
        self._adapters = lab_adapters() if adapters is None else adapters
        self._policy = default_policy() if policy is None else policy
        self._resolver = DurableAuthorizationResolver() if resolver is None else resolver
        if type(self._policy) is not ExecutionPolicy:
            raise ProviderError("policy_denied")
        self._lock = threading.Lock()
        self._spent = set()
        self._inflight = set()

    def __repr__(self):
        return "NeutralModelGateway(closed)"

    def execute(self, access, authorization_id, budget_microusd, resource_id, deployment_id,
                supplied_url=None, operation_id=QUESTION_ID):
        """Run one simulated call. The caller cannot supply the effective permission."""
        reject_caller_destination(supplied_url)
        if operation_id != QUESTION_ID:
            raise ProviderError("operation_denied")
        if type(self._resolver) is not LedgerDurableAuthorization:
            raise ProviderError("remote_not_authorized")
        deployment = self._registry.get(deployment_id)
        decision = self._resolver.resolve(
            access, authorization_id, deployment, resource_id, budget_microusd)
        if decision.allowed is not True or decision.reason != "accepted":
            raise ProviderError(decision.reason)
        if (decision.deployment_id != deployment.deployment_id
                or decision.provider_id != deployment.identity.provider_id
                or decision.model_id != deployment.identity.model_id
                or decision.organization_id != access.organization_id):
            raise ProviderError("remote_not_authorized")
        context = ExecutionContext(
            access.organization_id, access.principal_id, resource_id, PURPOSE, CLASSIFICATION, budget_microusd)
        grant = ExecutionGrant(
            deployment.identity.provider_id, deployment.deployment_id, access.organization_id,
            access.principal_id, resource_id, PURPOSE, CLASSIFICATION, REQUIRED, 1)
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
        if response.included_output_tokens is not None and (
                type(response.included_output_tokens) is not int
                or response.included_output_tokens > response.usage.output_tokens):
            raise ProviderError("consumption_ambiguous")
        check_observation(FIXED_DOCUMENT.encode("utf-8"), response.observation)
        self._resolver.consume(access, authorization_id)
        return GatewayResult(
            True, "accepted", deployment.deployment_id, context.organization_id,
            response.usage.input_tokens, response.usage.output_tokens, reservation,
            response.estimated_microusd, response.thoughts_tokens, response.cost_exact,
            response.thoughts_inferred, response.tool_inferred,
            response.prompt_inferred, response.visible_inferred,
            response.included_output_tokens)

    def public_state(self, result, organization_id):
        if type(result) is not GatewayResult or result.organization_id != organization_id:
            raise ProviderError("remote_not_authorized")
        return {
            "phase": "completed" if result.accepted else "denied",
            "reason": result.reason,
            "organization_id": result.organization_id,
            "deployment_id": result.deployment_id,
        }
