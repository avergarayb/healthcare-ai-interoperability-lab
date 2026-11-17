"""Operational model gateway. Authorization comes from the durable resolver, not a caller grant."""
import threading

from app.enterprise_llm_providers.errors import ProviderError
from app.enterprise_llm_providers.permit import CLASSIFICATION, PURPOSE
from app.enterprise_llm_providers.schema import QUESTION_ID
from app.enterprise_llm_providers.smoke import FIXED_DOCUMENT
from app.enterprise_llm_providers.validation import check_observation

from app.enterprise_ai_processing.durable_resolver import LedgerDurableAuthorization

from .adapters import lab_adapters
from .egress import OperationalEgressConsent, arm_openai_adapter, bind_consent
from .egress_gemini import OperationalGeminiConsent, arm_gemini_adapter, bind_gemini_consent
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
        self._clinical_spent = set()
        self._clinical_inflight = set()
        self._external_spent = set()
        self._external_inflight = set()
        self._jurisdiction_spent = set()
        self._jurisdiction_inflight = set()

    def __repr__(self):
        return "NeutralModelGateway(closed)"

    def execute(self, access, authorization_id, budget_microusd, resource_id, deployment_id,
                supplied_url=None, operation_id=QUESTION_ID, egress_consent=None):
        """Run one call. Without consent the adapter stays offline and send stays closed."""
        reject_caller_destination(supplied_url)
        if operation_id != QUESTION_ID:
            raise ProviderError("operation_denied")
        if type(self._resolver) is not LedgerDurableAuthorization:
            raise ProviderError("remote_not_authorized")
        deployment = self._registry.get(deployment_id)
        if egress_consent is not None:
            if type(egress_consent) is OperationalEgressConsent:
                bind_consent(egress_consent, access, deployment, resource_id, budget_microusd)
            elif type(egress_consent) is OperationalGeminiConsent:
                bind_gemini_consent(
                    egress_consent, access, deployment, resource_id, budget_microusd, authorization_id)
            else:
                raise ProviderError("egress_blocked")
        decision = self._resolver.resolve(
            access, authorization_id, deployment, resource_id, budget_microusd)
        if decision.allowed is not True or decision.reason != "accepted":
            raise ProviderError(decision.reason)
        if (decision.deployment_id != deployment.deployment_id
                or decision.provider_id != deployment.identity.provider_id
                or decision.model_id != deployment.identity.model_id
                or decision.organization_id != access.organization_id):
            raise ProviderError("remote_not_authorized")
        if egress_consent is not None:
            hold = self._resolver.confirm_hold(
                access, authorization_id, deployment, resource_id, budget_microusd)
            if hold != "accepted":
                raise ProviderError(hold)
        context = ExecutionContext(
            access.organization_id, access.principal_id, resource_id, PURPOSE, CLASSIFICATION, budget_microusd)
        grant = ExecutionGrant(
            deployment.identity.provider_id, deployment.deployment_id, access.organization_id,
            access.principal_id, resource_id, PURPOSE, CLASSIFICATION, REQUIRED, 1)
        with self._lock:
            if deployment.deployment_id in self._spent or deployment.deployment_id in self._inflight:
                raise ProviderError("replay_denied")
            authorize(context, grant, deployment)
            if egress_consent is None:
                adapter = self._adapters.get(deployment.deployment_id)
            elif type(egress_consent) is OperationalEgressConsent:
                adapter = arm_openai_adapter(
                    self._resolver.clock(), egress_consent, access, deployment, resource_id)
            elif type(egress_consent) is OperationalGeminiConsent:
                adapter = arm_gemini_adapter(
                    self._resolver.clock(), egress_consent, access, deployment, resource_id,
                    authorization_id)
            else:
                raise ProviderError("egress_blocked")
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
        cost_exact = response.cost_exact
        cost_kind = None
        if egress_consent is not None:
            cost_exact = False
            cost_kind = "estimated" if response.estimated_microusd is not None else "uncertain"
        return GatewayResult(
            True, "accepted", deployment.deployment_id, context.organization_id,
            response.usage.input_tokens, response.usage.output_tokens, reservation,
            response.estimated_microusd, response.thoughts_tokens, cost_exact,
            response.thoughts_inferred, response.tool_inferred,
            response.prompt_inferred, response.visible_inferred,
            response.included_output_tokens,             response.provider_request_id,
            response.response_status, cost_kind)

    def execute_lab_summary(self, access, authorization_id, budget_microusd, resource_id,
                            deployment_id, chart, consent, before_consume):
        """One clinical summary. The vacation fixture and its consent cannot enter."""
        from app.clinical_lab_summary.consent import OperationalClinicalConsent, bind_clinical_consent
        from app.clinical_lab_summary.context import require_model_context
        from app.clinical_lab_summary.model import ClinicalResult, arm_clinical_adapter, validate_summary
        from app.clinical_lab_summary.policy import DEPLOYMENT_ID, OPERATION_ID as CLINICAL_OPERATION
        from app.clinical_lab_summary.policy import POLICY_REF as CLINICAL_POLICY

        if type(consent) is not OperationalClinicalConsent or not callable(before_consume):
            raise ProviderError("egress_blocked")
        if deployment_id != DEPLOYMENT_ID:
            raise ProviderError("model_denied")
        minimized = require_model_context(chart, resource_id)
        deployment = self._registry.get(deployment_id)
        bind_clinical_consent(
            consent, access, deployment, resource_id, budget_microusd, authorization_id)
        decision = self._resolver.resolve(
            access, authorization_id, deployment, resource_id, budget_microusd,
            operation_id=CLINICAL_OPERATION, policy_ref=CLINICAL_POLICY)
        if decision.allowed is not True or decision.reason != "accepted":
            raise ProviderError(decision.reason)
        if (decision.deployment_id != deployment.deployment_id
                or decision.provider_id != deployment.identity.provider_id
                or decision.model_id != deployment.identity.model_id
                or decision.organization_id != access.organization_id):
            raise ProviderError("remote_not_authorized")
        hold = self._resolver.confirm_hold(
            access, authorization_id, deployment, resource_id, budget_microusd,
            operation_id=CLINICAL_OPERATION, policy_ref=CLINICAL_POLICY)
        if hold != "accepted":
            raise ProviderError(hold)
        adapter = arm_clinical_adapter(
            self._resolver.clock(), consent, access, deployment, resource_id, authorization_id)
        reservation = adapter.estimate(deployment)
        if reservation != deployment.reservation_microusd or budget_microusd < reservation:
            raise ProviderError("budget_exceeded")
        with self._lock:
            if authorization_id in self._clinical_spent or authorization_id in self._clinical_inflight:
                raise ProviderError("replay_denied")
            self._clinical_inflight.add(authorization_id)
        try:
            response = adapter.invoke_once(minimized)
        except ProviderError as error:
            with self._lock:
                self._clinical_inflight.discard(authorization_id)
                self._clinical_spent.add(authorization_id)
            raise ProviderError(error.reason, getattr(error, "diagnostic", None)) from None
        with self._lock:
            self._clinical_inflight.discard(authorization_id)
            self._clinical_spent.add(authorization_id)
        summary = validate_summary(minimized, response.parsed)
        try:
            before_consume(summary)
        except ProviderError:
            raise
        except Exception:
            raise ProviderError("review_unavailable") from None
        self._resolver.consume(access, authorization_id)
        return ClinicalResult(
            True, "accepted", deployment.deployment_id, access.organization_id,
            response.input_tokens, response.output_tokens, reservation,
            response.estimated_microusd, False, "estimated",
            response.provider_request_id, response.response_status, summary)

    def execute_external_summary(self, access, authorization_id, budget_microusd, resource_id,
                                 deployment_id, chart, consent, before_consume):
        """One external summary. Clinical and vacation consents cannot enter."""
        from app.external_fhir.consent import OperationalExternalConsent, bind_external_consent
        from app.external_fhir.context import require_model_context, validate_summary
        from app.external_fhir.model import ExternalResult, arm_external_adapter
        from app.external_fhir.policy import DEPLOYMENT_ID, OPERATION_ID as EXTERNAL_OPERATION
        from app.external_fhir.policy import POLICY_REF as EXTERNAL_POLICY

        if type(consent) is not OperationalExternalConsent or not callable(before_consume):
            raise ProviderError("egress_blocked")
        if deployment_id != DEPLOYMENT_ID:
            raise ProviderError("model_denied")
        minimized = require_model_context(chart, resource_id)
        deployment = self._registry.get(deployment_id)
        bind_external_consent(
            consent, access, deployment, resource_id, budget_microusd, authorization_id)
        decision = self._resolver.resolve(
            access, authorization_id, deployment, resource_id, budget_microusd,
            operation_id=EXTERNAL_OPERATION, policy_ref=EXTERNAL_POLICY)
        if decision.allowed is not True or decision.reason != "accepted":
            raise ProviderError(decision.reason)
        if (decision.deployment_id != deployment.deployment_id
                or decision.provider_id != deployment.identity.provider_id
                or decision.model_id != deployment.identity.model_id
                or decision.organization_id != access.organization_id):
            raise ProviderError("remote_not_authorized")
        hold = self._resolver.confirm_hold(
            access, authorization_id, deployment, resource_id, budget_microusd,
            operation_id=EXTERNAL_OPERATION, policy_ref=EXTERNAL_POLICY)
        if hold != "accepted":
            raise ProviderError(hold)
        adapter = arm_external_adapter(consent, access, deployment, resource_id, authorization_id)
        reservation = adapter.estimate(deployment)
        if reservation != deployment.reservation_microusd or budget_microusd < reservation:
            raise ProviderError("budget_exceeded")
        with self._lock:
            if authorization_id in self._external_spent or authorization_id in self._external_inflight:
                raise ProviderError("replay_denied")
            if authorization_id in self._clinical_spent or authorization_id in self._spent:
                raise ProviderError("replay_denied")
            self._external_inflight.add(authorization_id)
        try:
            response = adapter.invoke_once(minimized)
        except ProviderError as error:
            with self._lock:
                self._external_inflight.discard(authorization_id)
                self._external_spent.add(authorization_id)
            raise ProviderError(error.reason, getattr(error, "diagnostic", None)) from None
        with self._lock:
            self._external_inflight.discard(authorization_id)
            self._external_spent.add(authorization_id)
        summary = validate_summary(minimized, response.parsed)
        try:
            before_consume(summary)
        except ProviderError:
            raise
        except Exception:
            raise ProviderError("review_unavailable") from None
        self._resolver.consume(access, authorization_id)
        return ExternalResult(
            True, "accepted", deployment.deployment_id, access.organization_id,
            response.input_tokens, response.output_tokens, reservation,
            response.estimated_microusd, False, "estimated",
            response.provider_request_id, response.response_status, summary)

    def execute_jurisdiction_summary(self, access, authorization_id, budget_microusd, resource_id,
                                     deployment_id, chart, consent, profile, before_consume):
        """One jurisdiction summary. External, clinical, and vacation consents cannot enter."""
        from app.jurisdiction_lab.consent import OperationalJurisdictionConsent, bind_jurisdiction_consent
        from app.jurisdiction_lab.context import require_model_context, validate_summary
        from app.jurisdiction_lab.model import JurisdictionResult, arm_jurisdiction_adapter
        from app.jurisdiction_lab.policy import DEPLOYMENT_ID
        from app.jurisdiction_lab.profile import OPERATION_ID as JURISDICTION_OPERATION

        if type(consent) is not OperationalJurisdictionConsent or not callable(before_consume):
            raise ProviderError("egress_blocked")
        if deployment_id != DEPLOYMENT_ID or consent._policy_ref != profile.policy_ref:
            raise ProviderError("model_denied")
        minimized = require_model_context(chart, profile)
        deployment = self._registry.get(deployment_id)
        bind_jurisdiction_consent(
            consent, access, deployment, resource_id, budget_microusd, authorization_id)
        decision = self._resolver.resolve(
            access, authorization_id, deployment, resource_id, budget_microusd,
            operation_id=JURISDICTION_OPERATION, policy_ref=profile.policy_ref)
        if decision.allowed is not True or decision.reason != "accepted":
            raise ProviderError(decision.reason)
        if (decision.deployment_id != deployment.deployment_id
                or decision.provider_id != deployment.identity.provider_id
                or decision.model_id != deployment.identity.model_id
                or decision.organization_id != access.organization_id):
            raise ProviderError("remote_not_authorized")
        hold = self._resolver.confirm_hold(
            access, authorization_id, deployment, resource_id, budget_microusd,
            operation_id=JURISDICTION_OPERATION, policy_ref=profile.policy_ref)
        if hold != "accepted":
            raise ProviderError(hold)
        adapter = arm_jurisdiction_adapter(
            consent, access, deployment, resource_id, authorization_id, profile)
        reservation = adapter.estimate(deployment)
        if reservation != deployment.reservation_microusd or budget_microusd < reservation:
            raise ProviderError("budget_exceeded")
        with self._lock:
            if authorization_id in self._jurisdiction_spent or authorization_id in self._jurisdiction_inflight:
                raise ProviderError("replay_denied")
            if authorization_id in self._external_spent or authorization_id in self._clinical_spent or authorization_id in self._spent:
                raise ProviderError("replay_denied")
            self._jurisdiction_inflight.add(authorization_id)
        try:
            response = adapter.invoke_once(minimized)
        except ProviderError as error:
            with self._lock:
                self._jurisdiction_inflight.discard(authorization_id)
                self._jurisdiction_spent.add(authorization_id)
            raise ProviderError(error.reason, getattr(error, "diagnostic", None)) from None
        with self._lock:
            self._jurisdiction_inflight.discard(authorization_id)
            self._jurisdiction_spent.add(authorization_id)
        summary = validate_summary(minimized, response.parsed, profile)
        try:
            before_consume(summary)
        except ProviderError:
            raise
        except Exception:
            raise ProviderError("review_unavailable") from None
        self._resolver.consume(access, authorization_id)
        return JurisdictionResult(
            True, "accepted", deployment.deployment_id, access.organization_id,
            response.input_tokens, response.output_tokens, reservation,
            response.estimated_microusd, False, "estimated",
            response.provider_request_id, response.response_status, summary)

    def public_state(self, result, organization_id):
        if type(result) is not GatewayResult or result.organization_id != organization_id:
            raise ProviderError("remote_not_authorized")
        return {
            "phase": "completed" if result.accepted else "denied",
            "reason": result.reason,
            "organization_id": result.organization_id,
            "deployment_id": result.deployment_id,
        }
