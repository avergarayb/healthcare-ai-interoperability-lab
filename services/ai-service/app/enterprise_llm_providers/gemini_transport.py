"""Gemini SDK transport. The default does not build a client, and send() does not call the API."""
import os

from google import genai
from google.genai import types

from .errors import ProviderError
from .gemini_configuration import ALLOWED_MODEL, TIMEOUT_MILLISECONDS
from .gemini_request import require_closed_generation
from .smoke import FIXED_DOCUMENT


OFFICIAL_ORIGIN = "https://generativelanguage.googleapis.com"
_REDIRECT_ENV = (
    "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy",
    "GEMINI_BASE_URL", "GOOGLE_GENAI_BASE_URL",
)


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


def open_official_client(credential):
    """Build the official client. Construction does not call generateContent."""
    for name in _REDIRECT_ENV:
        if os.environ.get(name):
            raise ProviderError("environment_redirect")
    if type(credential) is not str or credential == "":
        raise ProviderError("credential_absent")
    client = genai.Client(
        api_key=credential,
        http_options=types.HttpOptions(
            timeout=TIMEOUT_MILLISECONDS,
            retry_options=types.HttpRetryOptions(attempts=1),
        ),
    )
    if not _official(client):
        raise ProviderError("not_configured")
    return client


def require_official_client(client):
    if not _official(client):
        raise ProviderError("not_configured")


def _official(client):
    options = getattr(getattr(client, "_api_client", None), "_http_options", None)
    if options is None or options.timeout != TIMEOUT_MILLISECONDS:
        return False
    retry = getattr(options, "retry_options", None)
    if retry is None or retry.attempts != 1:
        return False
    base = getattr(options, "base_url", None)
    if type(base) is not str or not base.startswith("https://"):
        return False
    host = base[len("https://"):].split("/", 1)[0]
    return host == "generativelanguage.googleapis.com"


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
    diagnostic = _safe_diagnostic(response)
    if _reported_model(response) != ALLOWED_MODEL:
        raise ProviderError("model_denied", diagnostic)
    reason = diagnostic["finish_reason"]
    if reason in {"SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII"}:
        raise ProviderError("model_refusal", diagnostic)
    if reason == "MAX_TOKENS":
        raise ProviderError("incomplete_output", diagnostic)
    if reason != "STOP":
        raise ProviderError("incomplete_output", diagnostic)
    text = getattr(response, "text", None)
    if type(text) is not str or text.strip() == "":
        raise ProviderError("incomplete_output", diagnostic)
    account = _account(getattr(response, "usage_metadata", None))
    if account["usable"] is not True:
        raise ProviderError("consumption_ambiguous", diagnostic)
    return {
        "status": "completed",
        "output": [{"type": "message", "content": [{"type": "output_text", "text": text}]}],
        "usage": {
            "input_tokens": account["input_tokens"],
            "output_tokens": account["output_tokens"],
            "thoughts_tokens": account["thoughts_tokens"],
            "cost_exact": account["cost_exact"],
            "prompt_inferred": account["prompt_inferred"],
            "visible_inferred": account["visible_inferred"],
            "thoughts_inferred": account["thoughts_inferred"],
            "tool_inferred": account["tool_inferred"],
        },
    }


def _reported_model(response):
    """The installed SDK publishes model_version. Older stand-ins used model."""
    reported = getattr(response, "model", None)
    if type(reported) is not str or reported == "":
        reported = getattr(response, "model_version", None)
    if type(reported) is str and reported.startswith("models/"):
        reported = reported[len("models/"):]
    return reported


def _safe_diagnostic(response):
    """Finish and token counts only. Text, thoughts and messages stay out."""
    candidates = getattr(response, "candidates", None)
    candidate_present = type(candidates) is list and len(candidates) == 1
    content = getattr(candidates[0], "content", None) if candidate_present else None
    reason = _finish_reason(response)
    account = _account(getattr(response, "usage_metadata", None))
    return {
        "finish_reason": reason if reason != "" else "absent",
        "candidate_present": candidate_present,
        "content_present": content is not None,
        "usage_present": getattr(response, "usage_metadata", None) is not None,
        "input_tokens": account["input_tokens"],
        "candidate_tokens": account["candidate_tokens"],
        "thoughts_tokens": account["thoughts_tokens"],
        "output_tokens": account["output_tokens"],
        "cost_exact": account["cost_exact"],
        "prompt_inferred": account["prompt_inferred"],
        "visible_inferred": account["visible_inferred"],
        "thoughts_inferred": account["thoughts_inferred"],
        "tool_inferred": account["tool_inferred"],
    }


def _read_count(value):
    if value is None:
        return "absent", None
    if type(value) is int and value >= 0:
        return "present", value
    return "invalid", None


def _reconcile(state, total):
    present = {key: value for key, (kind, value) in state.items() if kind == "present"}
    missing = [key for key, (kind, _value) in state.items() if kind == "absent"]
    known = sum(present.values())
    if known > total or (not missing and known != total):
        return state, True
    if len(missing) == 1:
        updated = dict(state)
        updated[missing[0]] = ("present", total - known)
        return updated, False
    if missing and known == total:
        updated = dict(state)
        for key in missing:
            updated[key] = ("present", 0)
        return updated, False
    return state, False


def _account(usage):
    """Classify optional Gemini usage fields. Absent thoughts are not zero."""
    names = {
        "prompt": "prompt_token_count",
        "visible": "candidates_token_count",
        "thoughts": "thoughts_token_count",
        "tool": "tool_use_prompt_token_count",
    }
    state = {key: _read_count(getattr(usage, attr, None)) for key, attr in names.items()}
    reported = {key: kind for key, (kind, _value) in state.items()}
    invalid = any(kind == "invalid" for kind, _value in state.values())
    total_kind, total = _read_count(getattr(usage, "total_token_count", None))
    inconsistent = False
    if total_kind == "invalid":
        invalid = True
    elif total_kind == "present" and invalid is not True:
        state, inconsistent = _reconcile(state, total)
    prompt_kind, prompt = state["prompt"]
    visible_kind, visible = state["visible"]
    thought_kind, thoughts = state["thoughts"]
    tool_kind, tool = state["tool"]
    usable = invalid is not True and inconsistent is not True and prompt_kind == "present" and visible_kind == "present"
    exact = usable and thought_kind == "present"
    incoming = prompt + (tool if tool_kind == "present" else 0) if prompt_kind == "present" else None

    def inferred(key, kind):
        return usable and reported[key] == "absent" and kind == "present"

    return {
        "input_tokens": incoming,
        "candidate_tokens": visible if visible_kind == "present" else None,
        "thoughts_tokens": thoughts if thought_kind == "present" else None,
        "output_tokens": visible if visible_kind == "present" else None,
        "cost_exact": exact,
        "usable": usable,
        "prompt_inferred": inferred("prompt", prompt_kind),
        "visible_inferred": inferred("visible", visible_kind),
        "thoughts_inferred": inferred("thoughts", thought_kind),
        "tool_inferred": inferred("tool", tool_kind),
    }


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
