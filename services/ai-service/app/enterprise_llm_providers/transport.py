"""SDK transport. Egress stays closed; the default transport never builds a client."""
import os
import httpx2
from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI

from .configuration import ALLOWED_MODEL
from .errors import ProviderError


TIMEOUT_SECONDS = 15.0
OFFICIAL_HOST = "api.openai.com"


def live_egress_enabled():
    """Closed until a later Product Owner authorization changes this function."""
    return False


class DisabledOpenAITransport:
    """Default transport. It does not construct an SDK client."""

    def __repr__(self):
        return "DisabledOpenAITransport(no-network)"

    def send(self, payload, timeout_seconds):
        raise ProviderError("remote_disabled")


class OpenAISDKTransport:
    """Official client with retries disabled. send() cannot leave the process."""

    def __init__(self, credential):
        if type(credential) is not str or credential == "":
            raise ProviderError("credential_absent")
        self._credential = credential
        self._client = OpenAI(
            api_key=credential,
            max_retries=0,
            timeout=httpx2.Timeout(TIMEOUT_SECONDS),
        )
        if self._client.max_retries != 0 or _timeout_seconds(self._client.timeout) != TIMEOUT_SECONDS:
            raise ProviderError("not_configured")
        if _host(self._client.base_url) != OFFICIAL_HOST:
            raise ProviderError("not_configured")

    def __repr__(self):
        return "OpenAISDKTransport(egress-blocked)"

    def __reduce_ex__(self, protocol):
        raise TypeError("SDK transport is not portable")

    @classmethod
    def from_mapping(cls, mapping):
        if type(mapping) is not dict:
            raise ProviderError("credential_absent")
        return cls(mapping.get("OPENAI_API_KEY"))

    def send(self, payload, timeout_seconds):
        require_closed_payload(payload, timeout_seconds)
        if _host(self._client.base_url) != OFFICIAL_HOST:
            raise ProviderError("not_configured")
        if live_egress_enabled() is not True:
            raise ProviderError("egress_blocked")
        return dispatch_responses(self._client, payload, timeout_seconds)


def open_official_client(credential):
    """Build the closed client. Construction does not call Responses."""
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy",
                 "all_proxy", "OPENAI_BASE_URL", "OPENAI_CUSTOM_HEADERS"):
        if os.environ.get(name):
            raise ProviderError("environment_redirect")
    opened = OpenAISDKTransport(credential)
    client = opened._client
    if (client.max_retries != 0 or _timeout_seconds(client.timeout) != TIMEOUT_SECONDS
            or _host(client.base_url) != OFFICIAL_HOST):
        raise ProviderError("not_configured")
    return client


def dispatch_responses(client, payload, timeout_seconds):
    """One Responses call. Tests point the supplied client at an in-process transport."""
    require_closed_payload(payload, timeout_seconds)
    try:
        response = client.responses.create(
            model=payload["model"],
            instructions=payload["instructions"],
            input=payload["input"],
            store=False,
            service_tier="default",
            max_output_tokens=payload["max_output_tokens"],
            reasoning={"effort": "none"},
            stream=False,
            background=False,
            text=payload["text"],
            timeout=timeout_seconds,
        )
    except APITimeoutError:
        raise ProviderError("timeout") from None
    except APIStatusError as error:
        if error.status_code == 429:
            raise ProviderError("rate_limited") from None
        raise ProviderError("remote_unavailable") from None
    except APIConnectionError:
        raise ProviderError("network_unavailable") from None
    except ProviderError:
        raise
    except Exception:
        raise ProviderError("remote_unavailable") from None
    return _normalize(response)


def require_closed_payload(payload, timeout_seconds):
    if (type(payload) is not dict or timeout_seconds != TIMEOUT_SECONDS
            or payload.get("model") != ALLOWED_MODEL or payload.get("store") is not False
            or payload.get("service_tier") != "default" or payload.get("reasoning") != {"effort": "none"}
            or payload.get("stream") is not False or payload.get("background") is not False
            or "tools" in payload or "previous_response_id" in payload or "base_url" in payload
            or type(payload.get("max_output_tokens")) is not int
            or not 16 <= payload["max_output_tokens"] <= 256):
        raise ProviderError("invalid_input")


def _normalize(response):
    if response.model != ALLOWED_MODEL:
        raise ProviderError("model_denied")
    output = []
    for item in response.output:
        if item.type != "message":
            raise ProviderError("invalid_output")
        content = []
        for part in item.content:
            if part.type == "refusal":
                raise ProviderError("model_refusal")
            if part.type != "output_text" or type(part.text) is not str:
                raise ProviderError("invalid_output")
            content.append({"type": "output_text", "text": part.text})
        output.append({"type": "message", "content": content})
    body = {"status": response.status or "incomplete", "model": response.model, "output": output}
    usage = response.usage
    if usage is not None:
        body["usage"] = {"input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens}
    return body


def _host(url):
    return getattr(url, "host", "")


def _timeout_seconds(timeout):
    if type(timeout) is int or type(timeout) is float:
        return float(timeout)
    return float(timeout.connect)
