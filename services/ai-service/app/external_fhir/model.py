"""One external model call through the existing Gemini transport."""
import json
from dataclasses import dataclass

from app.enterprise_llm_providers.errors import ProviderError
from app.enterprise_llm_providers.gemini_pricing import estimate_microusd
from app.enterprise_llm_providers.validation import usage_tokens
from app.model_gateway.sdk_bridge import gemini_operational_reservation

from .generation import build_external_generation
from .policy import OPERATION_ID


@dataclass(frozen=True, slots=True, repr=False)
class ExternalResult:
    accepted: bool
    reason: str
    deployment_id: str
    organization_id: str
    input_tokens: int
    output_tokens: int
    reserved_microusd: int
    estimated_microusd: int
    cost_exact: bool
    cost_kind: str
    provider_request_id: str | None
    response_status: str | None
    summary: dict

    def __repr__(self):
        return "ExternalResult(closed)"


class _ExternalAdapter:
    def __init__(self, transport):
        self._transport = transport

    def estimate(self, deployment):
        if deployment.identity.provider_id != "gemini" or deployment.egress_allowed is not False:
            raise ProviderError("model_denied")
        return gemini_operational_reservation()

    def invoke_once(self, chart):
        generation = build_external_generation(chart)
        body = self._transport.send(generation, 15)
        if type(body) is not dict or body.get("status") != "completed":
            raise ProviderError("invalid_output")
        try:
            parsed = json.loads(body["output"][0]["content"][0]["text"])
        except (KeyError, IndexError, TypeError, ValueError):
            raise ProviderError("invalid_output") from None
        reported = usage_tokens(body)
        if reported is None or not isinstance(parsed, dict):
            raise ProviderError("consumption_ambiguous" if reported is None else "invalid_output")
        usage = body.get("usage") if type(body) is dict else {}
        thoughts = usage.get("thoughts_tokens") if type(usage) is dict else None
        outgoing = reported[1] + thoughts if type(thoughts) is int else reported[1]
        request_id = body.get("provider_request_id")
        status = body.get("status")
        return _Observed(
            parsed, reported[0], reported[1], estimate_microusd(reported[0], outgoing),
            request_id if type(request_id) is str else None,
            status if type(status) is str else None)


@dataclass(frozen=True, slots=True)
class _Observed:
    parsed: dict
    input_tokens: int
    output_tokens: int
    estimated_microusd: int
    provider_request_id: str | None
    response_status: str | None


def arm_external_adapter(consent, access, deployment, resource_id, authorization_id):
    """Arm one intercepted send. A consent without an injected client does not open the network."""
    from app.enterprise_llm_providers.gemini_transport import ExternalDispatchGrant, dispatch_external

    class _Transport:
        def __init__(self):
            from app.enterprise_llm_providers.gemini_transport import open_authorized_client
            if consent._http_client is None:
                raise ProviderError("provider_send_blocked")
            release = consent.claim(access, deployment, resource_id, authorization_id)
            self._release = release
            self._client = open_authorized_client(consent._credential, consent._http_client)

        def send(self, generation, timeout_seconds):
            if timeout_seconds != 15 or self._release.spend() is not True:
                raise ProviderError("egress_blocked")
            return dispatch_external(self._client, generation, ExternalDispatchGrant())

    return _ExternalAdapter(_Transport())
