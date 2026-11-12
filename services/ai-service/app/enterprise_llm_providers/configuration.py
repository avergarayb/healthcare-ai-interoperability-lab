"""Remote provider settings. The default is disabled and holds no credential."""
from dataclasses import dataclass

from .errors import ProviderError


ALLOWED_MODEL = "gpt-6-luna"
_OUTPUT_MIN = 16
_OUTPUT_MAX = 256


@dataclass(frozen=True, slots=True, repr=False)
class ProviderSettings:
    enabled: bool
    model_id: str
    timeout_seconds: float
    max_output_tokens: int
    max_input_bytes: int
    max_call_microusd: int
    laboratory_cap_microusd: int
    _credential: str | None = None

    def __post_init__(self):
        if (type(self.enabled) is not bool or type(self.model_id) is not str
                or type(self.timeout_seconds) not in (int, float)
                or type(self.max_output_tokens) is not int or type(self.max_input_bytes) is not int
                or type(self.max_call_microusd) is not int or type(self.laboratory_cap_microusd) is not int
                or not (0 < self.timeout_seconds <= 60)
                or not (_OUTPUT_MIN <= self.max_output_tokens <= _OUTPUT_MAX)
                or not (1 <= self.max_input_bytes <= 2048)
                or self.max_call_microusd < 1 or self.laboratory_cap_microusd < self.max_call_microusd
                or (self._credential is not None and type(self._credential) is not str)):
            raise ProviderError("not_configured")

    def __repr__(self):
        return "ProviderSettings(enabled)" if self.enabled else "ProviderSettings(disabled)"

    def __reduce_ex__(self, protocol):
        raise TypeError("Provider settings are not portable")

    @property
    def credential_present(self):
        return type(self._credential) is str and self._credential != ""

    @classmethod
    def disabled(cls):
        return cls(False, ALLOWED_MODEL, 15, 256, 2048, 1000, 5_000_000, None)

    @classmethod
    def from_mapping(cls, mapping):
        if type(mapping) is not dict:
            raise ProviderError("not_configured")
        enabled = mapping.get("OPENAI_REMOTE_ENABLED", "0") == "1"
        model_id = mapping.get("OPENAI_MODEL", ALLOWED_MODEL)
        credential = mapping.get("OPENAI_API_KEY")
        if credential is not None and type(credential) is not str:
            raise ProviderError("not_configured")
        try:
            timeout = float(mapping.get("OPENAI_TIMEOUT_SECONDS", "15"))
            output_tokens = int(mapping.get("OPENAI_MAX_OUTPUT_TOKENS", "256"))
            call_budget = int(mapping.get("OPENAI_MAX_CALL_MICROUSD", "1000"))
            laboratory_cap = int(mapping.get("OPENAI_LAB_CAP_MICROUSD", "5000000"))
        except (TypeError, ValueError):
            raise ProviderError("not_configured") from None
        return cls(enabled, model_id, timeout, output_tokens, 2048, call_budget, laboratory_cap, credential)
