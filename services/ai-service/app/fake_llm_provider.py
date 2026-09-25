"""Deterministic provider for tests. Does not call Gemini."""

from __future__ import annotations

import json
from typing import Any, Optional, Union

from app.experimental_models import ExperimentalSummaryRequest
from app.llm_provider import LLMProvider, ProviderErrorKind, ProviderGeneration

ScriptItem = Union[str, dict[str, Any], ProviderGeneration]


class FakeLLMProvider(LLMProvider):
    def __init__(
        self,
        mode: str = "success",
        script: Optional[list[ScriptItem]] = None,
    ) -> None:
        self.mode = mode
        self.calls = 0
        self.prompts: list[str] = []
        self._turns: Optional[list[ScriptItem]] = None if script is None else list(script)

    def generate_summary(self, request: ExperimentalSummaryRequest) -> ProviderGeneration:
        return self._respond("Synthetic laboratory summary for SYN-076-001.")

    def generate_text(self, prompt: str) -> ProviderGeneration:
        self.prompts.append(prompt)
        if self._turns is not None:
            self.calls += 1
            if not self._turns:
                return ProviderGeneration(invocation_started=True, error="empty")
            return self._script_item(self._turns.pop(0))
        return self._respond("Synthetic generated text.")

    def _script_item(self, item: ScriptItem) -> ProviderGeneration:
        if isinstance(item, ProviderGeneration):
            return item
        if isinstance(item, dict):
            return ProviderGeneration(invocation_started=True, text=json.dumps(item))
        return ProviderGeneration(invocation_started=True, text=item)

    def _respond(self, success_text: str) -> ProviderGeneration:
        self.calls += 1
        if self.mode == "success":
            return ProviderGeneration(invocation_started=True, text=success_text)
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
