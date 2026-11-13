"""Offline adapters. They translate a neutral request and do not import a provider SDK."""
import hashlib

from app.enterprise_llm_providers.errors import ProviderError
from app.enterprise_llm_providers.schema import QUESTION_ID
from app.enterprise_llm_providers.smoke import FIXED_DOCUMENT

from .contracts import ModelCapabilities, ModelRequest, ModelResponse, UsageMetadata
from .sdk_bridge import GeminiSdkBridge, OpenAISdkBridge


class _OfflineProvider:
    protocol = ""

    def __init__(self, observation=None, usage=True):
        self.calls = 0
        self.last_protocol = None
        self._observation = _valid_observation() if observation is None else observation
        self._usage = usage

    def capabilities(self, deployment):
        return ModelCapabilities(deployment.capabilities)

    def validate_request(self, request, deployment):
        if (type(request) is not ModelRequest or request.use_case != QUESTION_ID
                or request.source_text != FIXED_DOCUMENT or deployment.endpoint is not None):
            raise ProviderError("invalid_input")
        self.last_protocol = self.protocol

    def estimate_cost(self, request, deployment):
        self.validate_request(request, deployment)
        return deployment.reservation_microusd

    def invoke_once(self, request, deployment):
        self.validate_request(request, deployment)
        self.calls += 1
        usage = None if self._usage is not True else UsageMetadata(40, 16)
        return self.normalize_response({
            "deployment_id": deployment.deployment_id,
            "protocol": self.protocol,
            "observation": self._observation,
            "usage": usage,
            "estimated_microusd": deployment.reservation_microusd,
        })

    def normalize_response(self, raw):
        if type(raw) is not dict or raw.get("protocol") != self.protocol:
            raise ProviderError("invalid_output")
        usage = raw.get("usage")
        if usage is not None and type(usage) is not UsageMetadata:
            raise ProviderError("consumption_ambiguous")
        return ModelResponse(
            raw["deployment_id"], raw.get("observation"), usage or UsageMetadata(None, None),
            raw["estimated_microusd"])


class OfflineResponsesAdapter(_OfflineProvider):
    """OpenAI-shaped payload, kept in process. This is not the SDK transport."""

    protocol = "offline-responses-shape"

    def validate_request(self, request, deployment):
        super().validate_request(request, deployment)
        if deployment.identity.provider_id != "openai":
            raise ProviderError("model_denied")


class OfflineGeminiAdapter(_OfflineProvider):
    """Gemini-shaped payload, kept in process. This is not the SDK transport."""

    protocol = "offline-generate-content-shape"

    def validate_request(self, request, deployment):
        super().validate_request(request, deployment)
        if deployment.identity.provider_id != "gemini":
            raise ProviderError("model_denied")


class PrivateCustomAdapter(_OfflineProvider):
    """A private JSON protocol. The agent does not see this shape."""

    protocol = "custom-json-v1"

    def validate_request(self, request, deployment):
        super().validate_request(request, deployment)
        if deployment.identity.provider_id != "private-custom":
            raise ProviderError("model_denied")
        digest = hashlib.sha256(request.source_text.encode("utf-8")).hexdigest()
        self.last_protocol = self.protocol + ":" + digest[:8]


def lab_adapters():
    return {
        "openai-offline-a": OfflineResponsesAdapter(),
        "gemini-offline-a": OfflineGeminiAdapter(),
        "private-offline-a": PrivateCustomAdapter(),
        "private-offline-b": PrivateCustomAdapter(),
        "text-only-offline-a": _OfflineProvider(),
        "openai-sdk-a": OpenAISdkBridge(),
        "gemini-sdk-a": GeminiSdkBridge(),
    }


def _valid_observation():
    encoded = FIXED_DOCUMENT.encode("utf-8")
    return {
        "question_id": QUESTION_ID, "evidence_found": True, "proposed_days": 20, "proposed_months": 12,
        "source_excerpt": FIXED_DOCUMENT, "evidence_start": 0, "evidence_end": len(encoded),
        "refusal_or_insufficient": False,
    }
