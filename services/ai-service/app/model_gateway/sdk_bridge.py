"""Neutral bridges over the existing provider adapters.

This module does not import a provider SDK. The SDK stays in the transport
that the adapter already owns. The default transport does not send.
"""
import json
from datetime import timedelta

from app.enterprise_llm_providers.adapter import OpenAIResponsesAdapter
from app.enterprise_llm_providers.configuration import ProviderSettings
from app.enterprise_llm_providers.errors import ProviderError
from app.enterprise_llm_providers.gemini_adapter import GeminiResponsesAdapter
from app.enterprise_llm_providers.gemini_configuration import GeminiSettings
from app.enterprise_llm_providers.gemini_permit import GeminiExecutionPermit
from app.enterprise_llm_providers.gemini_pricing import estimate_microusd as gemini_estimate
from app.enterprise_llm_providers.gemini_request import build_generation, request_bytes
from app.enterprise_llm_providers.permit import CLASSIFICATION, PURPOSE, RemoteExecutionPermit, SyntheticRead
from app.enterprise_llm_providers.pricing import estimate_microusd as openai_estimate
from app.enterprise_llm_providers.request import build_payload
from app.enterprise_llm_providers.schema import QUESTION_ID
from app.enterprise_llm_providers.smoke import FIXED_DOCUMENT
from app.enterprise_llm_providers.transport import DisabledOpenAITransport
from app.enterprise_llm_providers.gemini_transport import DisabledGeminiTransport
from app.enterprise_llm_providers.validation import parse_output, usage_tokens

from .contracts import ModelCapabilities, ModelRequest, ModelResponse, UsageMetadata


_INSTANCE = "synthetic-lab"


class _Capture:
    """One provider body, released when normalization ends. This is not a cache."""

    def __init__(self, inner):
        self.inner = inner
        self._body = None

    def send(self, payload, timeout_seconds):
        body = self.inner.send(payload, timeout_seconds)
        self.release()
        self._body = body
        return body

    def take(self):
        body = self._body
        self._body = None
        return body

    def release(self):
        self._body = None


def openai_reservation():
    settings = ProviderSettings.disabled()
    payload = build_payload(FIXED_DOCUMENT, settings)
    return openai_estimate(len(json.dumps(payload).encode("utf-8")), settings.max_output_tokens, ceiling=True)


def gemini_reservation():
    settings = GeminiSettings.disabled()
    generation = build_generation(FIXED_DOCUMENT, settings)
    return gemini_estimate(request_bytes(generation), settings.max_output_tokens)


class _SdkBridge:
    provider_id = ""

    def __init__(self, adapter, capture, clock):
        self._adapter = adapter
        self._capture = capture
        self._clock = clock
        self.calls = 0

    def capabilities(self, deployment):
        return ModelCapabilities(deployment.capabilities)

    def validate_request(self, request, deployment):
        if (type(request) is not ModelRequest or request.use_case != QUESTION_ID
                or request.source_text != FIXED_DOCUMENT or request.principal_id == ""
                or request.resource_id == "" or deployment.endpoint is not None
                or deployment.egress_allowed is not False
                or deployment.identity.provider_id != self.provider_id):
            raise ProviderError("invalid_input")

    def estimate_cost(self, request, deployment):
        self.validate_request(request, deployment)
        return self.reservation()

    def invoke_once(self, request, deployment):
        self.validate_request(request, deployment)
        self.calls += 1
        if self._adapter.settings.enabled is not True:
            raise ProviderError("remote_disabled")
        try:
            observed = self._adapter.observe(self._reading(request), self._permit(request))
            body = self._capture.take()
            try:
                if observed.accepted is not True or type(body) is not dict:
                    raise ProviderError("invalid_output")
                parsed = parse_output(body)
                reported = usage_tokens(body)
                if reported is None:
                    raise ProviderError("consumption_ambiguous")
                cost = self.reported_cost(reported)
            finally:
                del body
            return ModelResponse(
                deployment.deployment_id, parsed, UsageMetadata(reported[0], reported[1]), cost)
        finally:
            self._capture.release()

    def _reading(self, request):
        return SyntheticRead(
            request.organization_id, request.principal_id, _INSTANCE, request.resource_id,
            PURPOSE, CLASSIFICATION, QUESTION_ID, FIXED_DOCUMENT.encode("utf-8"))

    def _window(self):
        if self._clock is None:
            raise ProviderError("remote_not_authorized")
        now = self._clock()
        return now, now + timedelta(minutes=5)


class OpenAISdkBridge(_SdkBridge):
    provider_id = "openai"

    def __init__(self, settings=None, transport=None, clock=None):
        capture = _Capture(DisabledOpenAITransport() if transport is None else transport)
        adapter = OpenAIResponsesAdapter(
            ProviderSettings.disabled() if settings is None else settings, capture, clock)
        super().__init__(adapter, capture, clock)

    def reservation(self):
        return openai_reservation()

    def reported_cost(self, reported):
        return openai_estimate(reported[0], reported[1], ceiling=False)

    def _permit(self, request):
        start, end = self._window()
        return RemoteExecutionPermit(
            request.organization_id, request.principal_id, _INSTANCE, request.resource_id,
            PURPOSE, CLASSIFICATION, self.provider_id, "gpt-6-luna", QUESTION_ID, 1, start, end, True)


class GeminiSdkBridge(_SdkBridge):
    provider_id = "gemini"

    def __init__(self, settings=None, transport=None, clock=None):
        capture = _Capture(DisabledGeminiTransport() if transport is None else transport)
        adapter = GeminiResponsesAdapter(
            GeminiSettings.disabled() if settings is None else settings, capture, clock)
        super().__init__(adapter, capture, clock)

    def reservation(self):
        return gemini_reservation()

    def reported_cost(self, reported):
        return gemini_estimate(reported[0], reported[1])

    def _permit(self, request):
        start, end = self._window()
        return GeminiExecutionPermit(
            request.organization_id, request.principal_id, _INSTANCE, request.resource_id,
            PURPOSE, CLASSIFICATION, self.provider_id, "gemini-3.5-flash-lite", QUESTION_ID,
            1, start, end, True)
