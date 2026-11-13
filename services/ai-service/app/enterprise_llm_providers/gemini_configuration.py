"""Gemini settings. The default is disabled and holds no credential."""
from dataclasses import dataclass

from .errors import ProviderError


ALLOWED_MODEL = "gemini-3.5-flash-lite"
TIMEOUT_SECONDS = 15
TIMEOUT_MILLISECONDS = 15_000
MAX_OUTPUT_TOKENS = 128


@dataclass(frozen=True, slots=True, repr=False)
class GeminiSettings:
    enabled: bool
    model_id: str
    timeout_seconds: int
    max_output_tokens: int
    max_input_bytes: int
    max_call_microusd: int
    _credential: str | None = None

    def __post_init__(self):
        if (type(self.enabled) is not bool or type(self.model_id) is not str
                or type(self.timeout_seconds) is not int or type(self.max_output_tokens) is not int
                or type(self.max_input_bytes) is not int or type(self.max_call_microusd) is not int
                or self.timeout_seconds != TIMEOUT_SECONDS
                or not 64 <= self.max_output_tokens <= MAX_OUTPUT_TOKENS
                or not 1 <= self.max_input_bytes <= 2048 or self.max_call_microusd < 1
                or (self._credential is not None and type(self._credential) is not str)):
            raise ProviderError("not_configured")

    def __repr__(self):
        return "GeminiSettings(enabled)" if self.enabled else "GeminiSettings(disabled)"

    @property
    def credential_present(self):
        return type(self._credential) is str and self._credential != ""

    @classmethod
    def disabled(cls):
        return cls(False, ALLOWED_MODEL, TIMEOUT_SECONDS, MAX_OUTPUT_TOKENS, 2048, 1_000, None)

    @classmethod
    def from_mapping(cls, mapping):
        if type(mapping) is not dict:
            raise ProviderError("not_configured")
        enabled = mapping.get("GEMINI_REMOTE_ENABLED", "0") == "1"
        model_id = mapping.get("GEMINI_MODEL", ALLOWED_MODEL)
        credential = mapping.get("GEMINI_API_KEY")
        if credential is not None and type(credential) is not str:
            raise ProviderError("not_configured")
        return cls(enabled, model_id, TIMEOUT_SECONDS, MAX_OUTPUT_TOKENS, 2048, 1_000, credential)
