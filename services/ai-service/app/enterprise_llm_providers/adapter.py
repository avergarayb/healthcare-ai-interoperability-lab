"""One-shot Responses adapter. A failed or completed send cannot be repeated."""
import json
from dataclasses import dataclass

from .configuration import ALLOWED_MODEL, ProviderSettings
from .errors import ProviderError
from .permit import permit_matches
from .pricing import estimate_microusd
from .request import build_payload
from .transport import DisabledOpenAITransport
from .validation import check_observation, parse_output, usage_tokens


@dataclass(frozen=True, slots=True, repr=False)
class ProviderResult:
    accepted: bool
    reason: str
    days: int | None = None
    months: int | None = None
    provider_reported_input_tokens: int | None = None
    provider_reported_output_tokens: int | None = None
    estimated_microusd: int | None = None

    def __repr__(self):
        return "ProviderResult(in-process)"


class OpenAIResponsesAdapter:
    def __init__(self, settings=None, transport=None, clock=None):
        self.settings = ProviderSettings.disabled() if settings is None else settings
        if type(self.settings) is not ProviderSettings:
            raise ProviderError("not_configured")
        self._transport = DisabledOpenAITransport() if transport is None else transport
        self._clock = clock
        self._sent = False
        self._reserved_microusd = 0

    def __repr__(self):
        return "OpenAIResponsesAdapter(in-process)"

    def observe(self, reading, permit):
        if self._sent:
            raise ProviderError("replay_denied")
        settings = self.settings
        if settings.enabled is not True:
            raise ProviderError("remote_disabled")
        if settings.model_id != ALLOWED_MODEL:
            raise ProviderError("model_denied")
        if not settings.credential_present:
            raise ProviderError("credential_absent")
        now = self._clock() if self._clock is not None else None
        if not permit_matches(permit, reading, now):
            raise ProviderError("remote_not_authorized")
        try:
            document = reading.document.decode("utf-8")
        except (AttributeError, UnicodeError):
            raise ProviderError("invalid_input") from None
        if len(reading.document) > settings.max_input_bytes or document == "":
            raise ProviderError("invalid_input")
        payload = build_payload(document, settings)
        self._assert_closed_payload(payload, document)
        reservation = estimate_microusd(len(json.dumps(payload).encode("utf-8")),
                                        settings.max_output_tokens, ceiling=True)
        if (reservation > settings.max_call_microusd
                or self._reserved_microusd + reservation > settings.laboratory_cap_microusd):
            raise ProviderError("budget_exceeded")
        self._sent = True
        self._reserved_microusd += reservation
        body = self._send(payload, settings.timeout_seconds)
        parsed = parse_output(body)
        checked = check_observation(reading.document, parsed)
        reported = usage_tokens(body)
        if reported is None:
            raise ProviderError("consumption_ambiguous")
        reported_cost = estimate_microusd(reported[0], reported[1], ceiling=False)
        return ProviderResult(True, "accepted", checked.days, checked.months, reported[0], reported[1], reported_cost)

    def _send(self, payload, timeout_seconds):
        try:
            body = self._transport.send(payload, timeout_seconds)
        except ProviderError as error:
            raise ProviderError(error.reason) from None
        except TimeoutError:
            raise ProviderError("timeout") from None
        except Exception:
            raise ProviderError("remote_unavailable") from None
        if type(body) is not dict:
            raise ProviderError("invalid_output")
        return body

    def _assert_closed_payload(self, payload, document):
        encoded = str(payload)
        if (payload.get("store") is not False or "tools" in payload or "previous_response_id" in payload
                or "base_url" in payload or payload.get("stream") is not False
                or payload.get("background") is not False or payload.get("model") != ALLOWED_MODEL
                or payload.get("reasoning") != {"effort": "none"}
                or payload.get("service_tier") != "default"
                or self.settings._credential in encoded):
            raise ProviderError("invalid_input")
        if document not in payload["input"][0]["content"] or document in payload["instructions"]:
            raise ProviderError("invalid_input")
