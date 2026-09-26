from __future__ import annotations

import pytest

from app.experimental_fixture import CANONICAL_FIXTURE
from app.experimental_models import ExperimentalSummaryRequest
from app.fake_llm_provider import FakeLLMProvider
from app.gemini_provider import GeminiProvider
from app.llm_provider import LLMProvider, ProviderGeneration, build_experimental_prompt


class _TextResponse:
    def __init__(self, text) -> None:
        self.text = text


def test_llm_provider_declares_generate_summary_as_abstract():
    assert hasattr(LLMProvider, "generate_summary")
    assert getattr(LLMProvider.generate_summary, "__isabstractmethod__", False) is True
    assert not hasattr(LLMProvider, "generate_text")


def test_provider_without_generate_summary_cannot_be_instantiated():
    class IncompleteProvider(LLMProvider):
        pass

    with pytest.raises(TypeError):
        IncompleteProvider()


def test_fake_generate_summary_is_unchanged():
    request = ExperimentalSummaryRequest.model_validate(CANONICAL_FIXTURE)
    result = FakeLLMProvider("success").generate_summary(request)
    assert result == ProviderGeneration(
        invocation_started=True,
        text="Synthetic laboratory summary for SYN-076-001.",
    )


def test_gemini_generate_summary_normalizes_stubbed_response(monkeypatch):
    provider = GeminiProvider(api_key="test-key", model="gemini-flash-latest")
    seen: list[str] = []

    def fake_invoke(client, prompt: str):
        seen.append(prompt)
        return _TextResponse("  076 summary  ")

    monkeypatch.setattr(provider, "_invoke", fake_invoke)
    request = ExperimentalSummaryRequest.model_validate(CANONICAL_FIXTURE)
    result = provider.generate_summary(request)
    assert seen == [build_experimental_prompt(request)]
    assert result.text == "076 summary"
    assert not hasattr(provider, "generate_text")
