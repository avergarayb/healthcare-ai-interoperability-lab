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
        return self._generate_from_prompt(prompt)

    def generate_structured(
        self,
        *,
        system_instruction: str,
        contents: str,
        response_json_schema: dict,
        max_output_tokens: int,
    ) -> ProviderGeneration:
        """One JSON generation. No tools, no agent loop, and no SDK retry."""
        from google import genai
        from google.genai import types

        client = genai.Client(
            api_key=self._api_key,
            http_options=types.HttpOptions(
                timeout=int(PROVIDER_TIMEOUT_SECONDS * 1000),
                retry_options=types.HttpRetryOptions(attempts=1),
            ),
        )
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            response_json_schema=response_json_schema,
            max_output_tokens=max_output_tokens,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            thinking_config=_structured_thinking_config(self._model),
        )
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(self._invoke_structured, client, contents, config)
                response = future.result(timeout=PROVIDER_TIMEOUT_SECONDS)
        except FuturesTimeout:
            return ProviderGeneration(invocation_started=True, error="timeout")
        except Exception as exc:
            status_code = _http_status(exc)
            kind = "http_4xx" if status_code is not None and 400 <= status_code <= 499 else "http_5xx"
            return ProviderGeneration(invocation_started=True, error=kind, status_code=status_code)
        if "MAX_TOKENS" in _finish_reasons(response):
            return ProviderGeneration(invocation_started=True, error="max_tokens")
        return self._normalize(response)

    def _generate_from_prompt(self, prompt: str) -> ProviderGeneration:
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
        except Exception as exc:
            status_code = _http_status(exc)
            kind = "http_4xx" if status_code is not None and 400 <= status_code <= 499 else "http_5xx"
            return ProviderGeneration(invocation_started=True, error=kind, status_code=status_code)
        return self._normalize(response)

    def _invoke(self, client, prompt: str):
        return client.models.generate_content(model=self._model, contents=prompt)

    def _invoke_structured(self, client, contents: str, config):
        return client.models.generate_content(
            model=self._model,
            contents=contents,
            config=config,
        )

    def _normalize(self, response) -> ProviderGeneration:
        text = getattr(response, "text", None)
        if not isinstance(text, str):
            return ProviderGeneration(invocation_started=True, error="malformed")
        stripped = text.strip()
        if stripped == "":
            return ProviderGeneration(invocation_started=True, error="empty")
        return ProviderGeneration(invocation_started=True, text=stripped)


def _structured_thinking_config(model: str):
    """Lowest thinking mode the configured model family accepts.

    ``gemini-flash-latest`` currently resolves to Gemini 3.8 Flash. That model
    rejects ``thinking_level=minimal`` and uses ``thinking_level``, not
    ``thinking_budget``. Its lowest supported level is ``low``. Gemini 2.5
    Flash can turn thinking off with ``thinking_budget=0``. The two fields are
    never sent together. The 1024 output-token bound stays for the JSON
    contract once thinking no longer consumes that budget.
    """
    from google.genai import types

    if model.casefold().startswith("gemini-2.5-flash"):
        return types.ThinkingConfig(thinking_budget=0)
    return types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW)


def _finish_reasons(response) -> tuple[str, ...]:
    candidates = getattr(response, "candidates", None) or ()
    reasons: list[str] = []
    for candidate in candidates:
        reason = getattr(candidate, "finish_reason", None)
        if reason is None:
            continue
        name = getattr(reason, "name", None)
        if isinstance(name, str) and name:
            reasons.append(name)
        else:
            reasons.append(str(reason))
    return tuple(reasons)


def _http_status(exc: BaseException) -> int | None:
    code = getattr(exc, "code", None)
    if isinstance(code, int):
        return code
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    if isinstance(status, int):
        return status
    return None
