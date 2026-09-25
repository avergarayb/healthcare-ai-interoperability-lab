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


def test_llm_provider_declares_generate_text_as_abstract():
    assert hasattr(LLMProvider, "generate_text")
    assert getattr(LLMProvider.generate_text, "__isabstractmethod__", False) is True


def test_provider_without_generate_text_cannot_be_instantiated():
    class IncompleteProvider(LLMProvider):
        def generate_summary(self, request: ExperimentalSummaryRequest) -> ProviderGeneration:
            return ProviderGeneration(invocation_started=False)

    with pytest.raises(TypeError):
        IncompleteProvider()


def test_fake_generate_text_success_returns_provider_generation():
    provider = FakeLLMProvider("success")
    result = provider.generate_text("any synthetic prompt")
    assert result == ProviderGeneration(invocation_started=True, text="Synthetic generated text.")
    assert provider.calls == 1


def test_fake_generate_text_reuses_error_modes():
    for mode in ("timeout", "http_4xx", "http_5xx", "malformed", "empty"):
        result = FakeLLMProvider(mode).generate_text("prompt")
        assert result.invocation_started is True
        assert result.text is None
        assert result.error == mode


def test_fake_generate_summary_is_unchanged():
    request = ExperimentalSummaryRequest.model_validate(CANONICAL_FIXTURE)
    result = FakeLLMProvider("success").generate_summary(request)
    assert result == ProviderGeneration(
        invocation_started=True,
        text="Synthetic laboratory summary for SYN-076-001.",
    )


def test_gemini_generate_text_normalizes_stubbed_response(monkeypatch):
    provider = GeminiProvider(api_key="test-key", model="gemini-flash-latest")
    seen: list[str] = []

    def fake_invoke(client, prompt: str):
        seen.append(prompt)
        return _TextResponse("  hello from generate_text  ")

    monkeypatch.setattr(provider, "_invoke", fake_invoke)
    result = provider.generate_text("raw prompt")
    assert seen == ["raw prompt"]
    assert result == ProviderGeneration(invocation_started=True, text="hello from generate_text")


def test_gemini_generate_text_maps_empty_and_malformed(monkeypatch):
    provider = GeminiProvider(api_key="test-key", model="gemini-flash-latest")
    monkeypatch.setattr(provider, "_invoke", lambda client, prompt: _TextResponse("   "))
    empty = provider.generate_text("prompt")
    assert empty.error == "empty"

    monkeypatch.setattr(provider, "_invoke", lambda client, prompt: _TextResponse(None))
    malformed = provider.generate_text("prompt")
    assert malformed.error == "malformed"


def test_gemini_generate_summary_does_not_call_generate_text(monkeypatch):
    provider = GeminiProvider(api_key="test-key", model="gemini-flash-latest")
    generate_text_calls: list[str] = []
    original = provider.generate_text

    def wrapped(prompt: str) -> ProviderGeneration:
        generate_text_calls.append(prompt)
        return original(prompt)

    monkeypatch.setattr(provider, "generate_text", wrapped)
    monkeypatch.setattr(provider, "_invoke", lambda client, prompt: _TextResponse("076 summary"))
    request = ExperimentalSummaryRequest.model_validate(CANONICAL_FIXTURE)
    result = provider.generate_summary(request)
    assert generate_text_calls == []
    assert result.text == "076 summary"
    assert build_experimental_prompt(request).startswith("This is synthetic laboratory data.")
