"""Closed deployment catalog. Callers cannot attach an inference endpoint."""
from app.enterprise_llm_providers.errors import ProviderError
from app.enterprise_llm_providers.gemini_pricing import estimate_microusd as gemini_estimate
from app.enterprise_llm_providers.pricing import estimate_microusd as openai_estimate

from .contracts import ModelDeployment, ModelIdentity
from .sdk_bridge import gemini_reservation, openai_reservation


_ORGS_A = frozenset({"ORG-A"})
_ORGS_B = frozenset({"ORG-B"})
_POLICY = "synthetic-only-no-retention-claim"


def _deployment(deployment_id, provider_id, model_id, location, capabilities, reservation, organizations):
    return ModelDeployment(
        deployment_id, ModelIdentity(provider_id, model_id), location, frozenset(capabilities),
        _POLICY, reservation, frozenset(organizations), False, None)


def lab_catalog():
    """Static laboratory deployments. None of them has a network endpoint."""
    return (
        _deployment("openai-offline-a", "openai", "gpt-6-luna", "external-blocked",
                    ("text", "structured_output", "usage_report", "reasoning_control", "token_accounting"),
                    openai_estimate(500, 256, ceiling=True), _ORGS_A),
        _deployment("gemini-offline-a", "gemini", "gemini-3.5-flash-lite", "external-blocked",
                    ("text", "structured_output", "usage_report", "reasoning_control", "token_accounting"),
                    gemini_estimate(500, 128), _ORGS_A),
        _deployment("private-offline-a", "private-custom", "private-vacation-extractor-v1", "local-process",
                    ("text", "structured_output", "usage_report"), 1, _ORGS_A),
        _deployment("private-offline-b", "private-custom", "private-vacation-extractor-v1", "local-process",
                    ("text", "structured_output", "usage_report"), 1, _ORGS_B),
        _deployment("text-only-offline-a", "lab-text", "text-only-lab-v1", "local-process",
                    ("text",), 1, _ORGS_A),
        _deployment("openai-sdk-a", "openai", "gpt-6-luna", "external-blocked",
                    ("text", "structured_output", "usage_report", "reasoning_control", "token_accounting"),
                    openai_reservation(), _ORGS_A),
        _deployment("gemini-sdk-a", "gemini", "gemini-3.5-flash-lite", "external-blocked",
                    ("text", "structured_output", "usage_report", "reasoning_control", "token_accounting"),
                    gemini_reservation(), _ORGS_A),
    )


class ProviderRegistry:
    def __init__(self, deployments=None):
        chosen = lab_catalog() if deployments is None else deployments
        self._items = {}
        for deployment in chosen:
            if deployment.endpoint is not None or deployment.egress_allowed is not False:
                raise ProviderError("destination_denied")
            if deployment.deployment_id in self._items:
                raise ProviderError("not_configured")
            self._items[deployment.deployment_id] = deployment

    def get(self, deployment_id):
        found = self._items.get(deployment_id)
        if found is None:
            raise ProviderError("model_unregistered")
        return found

    def register(self, deployment):
        raise ProviderError("destination_denied")


def reject_caller_destination(supplied_url):
    """A caller-supplied URL is never a destination, including an allowlisted host."""
    if supplied_url is not None:
        raise ProviderError("destination_denied")


def pin_resolution(first_address, next_address):
    """A future live client must stop when a pinned address changes."""
    if type(first_address) is not str or first_address == "" or first_address != next_address:
        raise ProviderError("destination_denied")
    return first_address


def reject_redirect(status_code):
    if status_code in {301, 302, 303, 307, 308}:
        raise ProviderError("destination_denied")
