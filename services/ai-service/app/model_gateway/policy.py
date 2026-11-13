"""Selection policy. A grant names one deployment and does not travel to another."""
from app.enterprise_llm_providers.errors import ProviderError
from app.enterprise_llm_providers.permit import CLASSIFICATION, PURPOSE

from .contracts import ExecutionContext, ExecutionGrant, ExecutionPolicy


REQUIRED = ("structured_output", "usage_report")


def default_policy():
    return ExecutionPolicy()


def authorize(context, grant, deployment):
    if (type(context) is not ExecutionContext or type(grant) is not ExecutionGrant
            or type(context.budget_microusd) is not int or context.budget_microusd < 0):
        raise ProviderError("remote_not_authorized")
    if (grant.provider_id != deployment.identity.provider_id
            or grant.deployment_id != deployment.deployment_id
            or grant.organization_id != context.organization_id
            or context.organization_id not in deployment.allowed_organizations
            or grant.organization_id not in deployment.allowed_organizations
            or grant.principal_id != context.principal_id or grant.principal_id == ""
            or grant.resource_id != context.resource_id or grant.resource_id == ""
            or context.purpose != PURPOSE or grant.purpose != PURPOSE
            or context.classification != CLASSIFICATION or grant.classification != CLASSIFICATION
            or type(grant.revision) is not int or grant.revision < 1
            or grant.required_capabilities != REQUIRED):
        raise ProviderError("remote_not_authorized")
    if not set(REQUIRED).issubset(deployment.capabilities):
        raise ProviderError("capability_denied")
    if deployment.egress_allowed is not False or deployment.endpoint is not None:
        raise ProviderError("destination_denied")
    if context.budget_microusd < deployment.reservation_microusd:
        raise ProviderError("budget_exceeded")
