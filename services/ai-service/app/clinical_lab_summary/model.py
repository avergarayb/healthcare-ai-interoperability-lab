"""One clinical model call through the authorized Gemini transport."""
import json
from dataclasses import dataclass

from app.enterprise_llm_providers.errors import ProviderError
from app.enterprise_llm_providers.gemini_pricing import estimate_microusd
from app.enterprise_llm_providers.validation import usage_tokens
from app.model_gateway.sdk_bridge import gemini_operational_reservation

from .generation import build_clinical_generation
from .policy import OPERATION_ID


@dataclass(frozen=True, slots=True, repr=False)
class ClinicalResult:
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
        return "ClinicalResult(closed)"


@dataclass(frozen=True, slots=True, repr=False)
class _Observed:
    parsed: dict
    input_tokens: int
    output_tokens: int
    estimated_microusd: int
    provider_request_id: str | None
    response_status: str | None


class _ClinicalAdapter:
    def __init__(self, transport):
        self._transport = transport

    def estimate(self, deployment):
        if deployment.identity.provider_id != "gemini" or deployment.egress_allowed is not False:
            raise ProviderError("model_denied")
        return gemini_operational_reservation()

    def invoke_once(self, chart):
        generation = build_clinical_generation(chart)
        body = self._transport.send(generation, 15)
        parsed = _parse_text(body)
        reported = usage_tokens(body)
        if reported is None:
            raise ProviderError("consumption_ambiguous")
        usage = body.get("usage") if type(body) is dict else {}
        thoughts = usage.get("thoughts_tokens") if type(usage) is dict else None
        outgoing = reported[1] + thoughts if type(thoughts) is int else reported[1]
        request_id = body.get("provider_request_id")
        status = body.get("status")
        return _Observed(
            parsed, reported[0], reported[1], estimate_microusd(reported[0], outgoing),
            request_id if type(request_id) is str else None,
            status if type(status) is str else None)


def arm_clinical_adapter(resolver_clock, consent, access, deployment, resource_id, authorization_id):
    """Arm one send. The clock is accepted so the caller stays on the ledger clock."""
    del resolver_clock
    from app.enterprise_llm_providers.gemini_transport import ClinicalDispatchGrant, dispatch_clinical

    class _Transport:
        def __init__(self):
            from app.enterprise_llm_providers.gemini_transport import open_authorized_client
            release = consent.claim(access, deployment, resource_id, authorization_id)
            self._release = release
            self._client = open_authorized_client(consent._credential, consent._http_client)

        def send(self, generation, timeout_seconds):
            if timeout_seconds != 15 or self._release.spend() is not True:
                raise ProviderError("egress_blocked")
            return dispatch_clinical(self._client, generation, ClinicalDispatchGrant())

    return _ClinicalAdapter(_Transport())


def validate_summary(chart, parsed):
    """Every cited fact must exist, and an observation value must appear in its statement."""
    if not isinstance(parsed, dict) or set(parsed) != {"kind", "statements", "review"}:
        raise ProviderError("invalid_output")
    if parsed["kind"] != OPERATION_ID or parsed["review"] != "pending_human_review":
        raise ProviderError("invalid_output")
    statements = parsed["statements"]
    if not isinstance(statements, list) or not statements or len(statements) > 8:
        raise ProviderError("invalid_output")
    known = {(item["source"], item["resourceType"], item["id"]): item for item in chart["facts"]}
    checked = []
    for item in statements:
        if not isinstance(item, dict) or set(item) != {"text", "sources"}:
            raise ProviderError("invalid_output")
        text = item["text"]
        if type(text) is not str or text.strip() == "" or len(text) > 400:
            raise ProviderError("invalid_output")
        sources = item["sources"]
        if not isinstance(sources, list) or not sources or len(sources) > 4:
            raise ProviderError("invalid_output")
        cited = []
        for source in sources:
            if not isinstance(source, dict) or set(source) != {"source", "resourceType", "id"}:
                raise ProviderError("invalid_output")
            key = (source["source"], source["resourceType"], source["id"])
            fact = known.get(key)
            if fact is None:
                raise ProviderError("invalid_output")
            if fact["resourceType"] == "Observation" and fact["value"] not in text:
                raise ProviderError("invalid_output")
            cited.append({"source": key[0], "resourceType": key[1], "id": key[2]})
        checked.append({"text": text, "sources": cited})
    return {"kind": OPERATION_ID, "review": "pending_human_review", "statements": checked}


def _parse_text(body):
    if type(body) is not dict or body.get("status") != "completed":
        raise ProviderError("invalid_output")
    try:
        text = body["output"][0]["content"][0]["text"]
        parsed = json.loads(text)
    except (KeyError, IndexError, TypeError, ValueError):
        raise ProviderError("invalid_output") from None
    if not isinstance(parsed, dict):
        raise ProviderError("invalid_output")
    return parsed
