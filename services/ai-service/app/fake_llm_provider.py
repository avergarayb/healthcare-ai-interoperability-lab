"""Deterministic provider for tests. Does not call Gemini."""

from __future__ import annotations

from app.experimental_models import ExperimentalSummaryRequest
from app.llm_provider import LLMProvider, ProviderErrorKind, ProviderGeneration


class FakeLLMProvider(LLMProvider):
    def __init__(self, mode: str = "success") -> None:
        self.mode = mode
        self.calls = 0

    def generate_summary(self, request: ExperimentalSummaryRequest) -> ProviderGeneration:
        self.calls += 1
        if self.mode == "success":
            return ProviderGeneration(
                invocation_started=True,
                text="Synthetic laboratory summary for SYN-076-001.",
            )
        if self.mode == "oversized":
            return ProviderGeneration(invocation_started=True, text="x" * 2001)
        if self.mode == "unexpected":
            return ProviderGeneration(
                invocation_started=True,
                text='{"requiresHumanReview": false, "modelCalled": false, "summary": "no"}',
            )
        error: ProviderErrorKind
        if self.mode == "timeout":
            error = "timeout"
        elif self.mode == "http_4xx":
            error = "http_4xx"
        elif self.mode == "http_5xx":
            error = "http_5xx"
        elif self.mode == "malformed":
            error = "malformed"
        elif self.mode == "empty":
            error = "empty"
        else:
            raise ValueError("unknown fake provider mode")
        return ProviderGeneration(invocation_started=True, error=error)
