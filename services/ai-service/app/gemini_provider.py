"""Gemini SDK adapter. The application service must not import google.genai."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

from app.experimental_models import ExperimentalSummaryRequest, PROVIDER_TIMEOUT_SECONDS
from app.llm_provider import LLMProvider, ProviderGeneration, build_experimental_prompt


class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str, model: str) -> None:
        if not api_key:
            raise ValueError("Gemini API key must be provided to the provider")
        if not model:
            raise ValueError("Gemini model must be provided to the provider")
        self._api_key = api_key
        self._model = model

    def generate_summary(self, request: ExperimentalSummaryRequest) -> ProviderGeneration:
        prompt = build_experimental_prompt(request)
        from google import genai
        from google.genai import types

        client = genai.Client(
            api_key=self._api_key,
            http_options=types.HttpOptions(timeout=int(PROVIDER_TIMEOUT_SECONDS * 1000)),
        )
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(self._invoke, client, prompt)
                response = future.result(timeout=PROVIDER_TIMEOUT_SECONDS)
        except FuturesTimeout:
            return ProviderGeneration(invocation_started=True, error="timeout")
        except Exception:
            return ProviderGeneration(invocation_started=True, error="http_5xx")
        return self._normalize(response)

    def _invoke(self, client, prompt: str):
        return client.models.generate_content(model=self._model, contents=prompt)

    def _normalize(self, response) -> ProviderGeneration:
        text = getattr(response, "text", None)
        if not isinstance(text, str):
            return ProviderGeneration(invocation_started=True, error="malformed")
        stripped = text.strip()
        if stripped == "":
            return ProviderGeneration(invocation_started=True, error="empty")
        return ProviderGeneration(invocation_started=True, text=stripped)
