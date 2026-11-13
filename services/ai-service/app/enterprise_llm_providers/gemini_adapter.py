"""One-shot Gemini adapter. A failed or completed send cannot be repeated."""
from dataclasses import dataclass

from .errors import ProviderError
from .gemini_configuration import ALLOWED_MODEL, GeminiSettings
from .gemini_permit import gemini_permit_matches
from .gemini_pricing import CALL_CEILING_MICROUSD, estimate_microusd
from .gemini_request import build_generation, request_bytes
from .gemini_transport import DisabledGeminiTransport
from .smoke import FIXED_DOCUMENT
from .validation import check_observation, parse_output, usage_tokens


@dataclass(frozen=True, slots=True, repr=False)
class GeminiResult:
    accepted: bool
    reason: str
    days: int | None = None
    months: int | None = None
    provider_reported_input_tokens: int | None = None
    provider_reported_output_tokens: int | None = None
    estimated_microusd: int | None = None
    reserved_microusd: int | None = None

    def __repr__(self):
        return "GeminiResult(in-process)"


class GeminiResponsesAdapter:
    def __init__(self, settings=None, transport=None, clock=None):
        self.settings = GeminiSettings.disabled() if settings is None else settings
        if type(self.settings) is not GeminiSettings:
            raise ProviderError("not_configured")
        self._transport = DisabledGeminiTransport() if transport is None else transport
        self._clock = clock
        self._sent = False

    def __repr__(self):
        return "GeminiResponsesAdapter(in-process)"

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
        now = self._clock() if callable(self._clock) else None
        if not gemini_permit_matches(permit, reading, now):
            raise ProviderError("remote_not_authorized")
        try:
            document = reading.document.decode("utf-8")
        except (AttributeError, UnicodeError):
            raise ProviderError("invalid_input") from None
        if document != FIXED_DOCUMENT or len(reading.document) > settings.max_input_bytes:
            raise ProviderError("invalid_input")
        generation = build_generation(document, settings)
        if settings._credential in str(generation):
            raise ProviderError("invalid_input")
        reservation = estimate_microusd(request_bytes(generation), settings.max_output_tokens)
        if reservation > settings.max_call_microusd or reservation > CALL_CEILING_MICROUSD:
            raise ProviderError("budget_exceeded")
        self._sent = True
        body = self._send(generation, settings.timeout_seconds)
        parsed = parse_output(body)
        checked = check_observation(reading.document, parsed)
        reported = usage_tokens(body)
        if reported is None:
            raise ProviderError("consumption_ambiguous")
        reported_cost = estimate_microusd(reported[0], reported[1])
        return GeminiResult(
            True, "accepted", checked.days, checked.months, reported[0], reported[1],
            reported_cost, reservation)

    def _send(self, generation, timeout_seconds):
        try:
            body = self._transport.send(generation, timeout_seconds)
        except ProviderError as error:
            raise ProviderError(error.reason) from None
        except TimeoutError:
            raise ProviderError("timeout") from None
        except Exception:
            raise ProviderError("remote_unavailable") from None
        if type(body) is not dict:
            raise ProviderError("invalid_output")
        return body
