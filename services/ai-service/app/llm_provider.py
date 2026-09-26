"""Provider abstraction. Implementations must not set governance fields."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal, Optional

from app.experimental_models import ExperimentalSummaryRequest, PROMPT_VERSION

ProviderErrorKind = Literal["timeout", "http_4xx", "http_5xx", "malformed", "empty"]


@dataclass(frozen=True)
class ProviderGeneration:
    invocation_started: bool
    text: Optional[str] = None
    error: Optional[ProviderErrorKind] = None
    status_code: Optional[int] = None


class LLMProvider(ABC):
    @abstractmethod
    def generate_summary(self, request: ExperimentalSummaryRequest) -> ProviderGeneration:
        """Return model text or a provider error. Never set requiresHumanReview."""


def build_experimental_prompt(request: ExperimentalSummaryRequest) -> str:
    payload = request.model_dump(by_alias=True)
    lines = [
        "This is synthetic laboratory data.",
        "Produce an informational summary only.",
        "Do not diagnose.",
        "Do not recommend treatment.",
        "Do not recommend medication.",
        "Do not make clinical decisions.",
        "Do not infer patient identity.",
        "Do not invent information not present in the input.",
        "Keep the response concise.",
        f"Prompt version: {PROMPT_VERSION}.",
        f"caseId={payload['caseId']}",
        f"patientAgeRange={payload['patientAgeRange']}",
        f"sex={payload['sex']}",
        f"encounterType={payload['encounterType']}",
    ]
    for observation in payload["observations"]:
        lines.append(
            "observation "
            f"code={observation['code']} display={observation['display']} "
            f"value={observation['value']} unit={observation['unit']}"
        )
    for medication in payload["medications"]:
        lines.append(f"medication code={medication['code']} display={medication['display']}")
    return "\n".join(lines)
