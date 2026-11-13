"""Gemini SDK transport. The default does not build a client, and send() does not call the API."""
from google import genai
from google.genai import types

from .errors import ProviderError
from .gemini_configuration import ALLOWED_MODEL, TIMEOUT_MILLISECONDS
from .gemini_request import require_closed_generation
from .smoke import FIXED_DOCUMENT


class DisabledGeminiTransport:
    """Default transport. It does not construct an SDK client."""

    def __repr__(self):
        return "DisabledGeminiTransport(no-network)"

    def send(self, generation, timeout_seconds):
        raise ProviderError("remote_disabled")


class GeminiSDKTransport:
    """Official client with one attempt. send() cannot leave the process."""

    def __init__(self, credential):
        if type(credential) is not str or credential == "":
            raise ProviderError("credential_absent")
        self._client = genai.Client(
            api_key=credential,
            http_options=types.HttpOptions(
                timeout=TIMEOUT_MILLISECONDS,
                retry_options=types.HttpRetryOptions(attempts=1),
            ),
        )
        options = self._client._api_client._http_options
        if options.timeout != TIMEOUT_MILLISECONDS or options.retry_options.attempts != 1:
            raise ProviderError("not_configured")

    def __repr__(self):
        return "GeminiSDKTransport(egress-blocked)"

    def __reduce_ex__(self, protocol):
        raise TypeError("Gemini transport is not portable")

    def send(self, generation, timeout_seconds):
        require_closed_generation(generation, FIXED_DOCUMENT)
        if timeout_seconds != 15:
            raise ProviderError("not_configured")
        raise ProviderError("egress_blocked")


def dispatch_generate(client, generation):
    """One generateContent call for an injected client. Production send() never calls this."""
    require_closed_generation(generation, FIXED_DOCUMENT)
    config = types.GenerateContentConfig(
        system_instruction=generation["system_instruction"],
        response_mime_type="application/json",
        response_json_schema=generation["response_json_schema"],
        max_output_tokens=generation["max_output_tokens"],
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.MINIMAL),
    )
    try:
        response = client.models.generate_content(
            model=generation["model"], contents=generation["contents"], config=config)
    except ProviderError:
        raise
    except Exception as error:
        raise ProviderError(_error_reason(error)) from None
    return normalize_response(response)


def normalize_response(response):
    if _reported_model(response) != ALLOWED_MODEL:
        raise ProviderError("model_denied")
    reason = _finish_reason(response)
    if reason in {"SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII"}:
        raise ProviderError("model_refusal")
    if reason == "MAX_TOKENS":
        raise ProviderError("incomplete_output")
    if reason != "STOP":
        raise ProviderError("incomplete_output")
    text = getattr(response, "text", None)
    if type(text) is not str or text.strip() == "":
        raise ProviderError("incomplete_output")
    usage = _usage(response)
    if usage is None:
        raise ProviderError("consumption_ambiguous")
    return {
        "status": "completed",
        "output": [{"type": "message", "content": [{"type": "output_text", "text": text}]}],
        "usage": {"input_tokens": usage[0], "output_tokens": usage[1]},
    }


def _reported_model(response):
    """The installed SDK publishes model_version. Older stand-ins used model."""
    reported = getattr(response, "model", None)
    if type(reported) is not str or reported == "":
        reported = getattr(response, "model_version", None)
    if type(reported) is str and reported.startswith("models/"):
        reported = reported[len("models/"):]
    return reported


def _usage(response):
    usage = getattr(response, "usage_metadata", None)
    prompt = getattr(usage, "prompt_token_count", None)
    candidates = getattr(usage, "candidates_token_count", None)
    thoughts = getattr(usage, "thoughts_token_count", None)
    if (type(prompt) is not int or type(candidates) is not int or type(thoughts) is not int
            or prompt < 0 or candidates < 0 or thoughts < 0):
        return None
    return prompt, candidates + thoughts


def _finish_reason(response):
    candidates = getattr(response, "candidates", None)
    if type(candidates) is not list or len(candidates) != 1:
        return ""
    reason = getattr(candidates[0], "finish_reason", None)
    name = getattr(reason, "name", None)
    if type(name) is str:
        return name
    if type(reason) is str:
        return reason
    return ""


def _error_reason(error):
    code = getattr(error, "code", None)
    if code == 429:
        return "rate_limited"
    if type(code) is int and code >= 500:
        return "remote_unavailable"
    name = type(error).__name__
    if name in {"TimeoutError", "ReadTimeout", "ConnectTimeout", "APITimeoutError"}:
        return "timeout"
    if name in {"ConnectError", "APIConnectionError"}:
        return "network_unavailable"
    return "remote_unavailable"
