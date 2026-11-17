"""SDK transport. Egress stays closed; the default transport never builds a client."""
import os
import re
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


def open_authorized_client(credential, timeout_seconds, http_client=None):
    """One official client for a spent release. Construction does not call Responses."""
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy",
                 "all_proxy", "OPENAI_BASE_URL", "OPENAI_CUSTOM_HEADERS"):
        if os.environ.get(name):
            raise ProviderError("environment_redirect")
    if type(credential) is not str or credential == "":
        raise ProviderError("credential_absent")
    if type(timeout_seconds) not in (int, float) or isinstance(timeout_seconds, bool):
        raise ProviderError("not_configured")
    client = OpenAI(
        api_key=credential, max_retries=0, timeout=httpx2.Timeout(float(timeout_seconds)),
        http_client=http_client)
    if client.max_retries != 0 or _host(client.base_url) != OFFICIAL_HOST:
        raise ProviderError("not_configured")
    if getattr(client.base_url, "scheme", "") != "https":
        raise ProviderError("not_configured")
    return client


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
        raise ProviderError("timeout", {"http_status": None, "usage_present": False, "cost_exact": False}) from None
    except APIStatusError as error:
        code = error.status_code if type(error.status_code) is int else None
        reason = "rate_limited" if code == 429 else "remote_unavailable"
        raise ProviderError(reason, {"http_status": code, "usage_present": False, "cost_exact": False}) from None
    except APIConnectionError:
        raise ProviderError("network_unavailable", {"usage_present": False, "cost_exact": False}) from None
    except ProviderError:
        raise
    except Exception:
        raise ProviderError("remote_unavailable") from None
    return _normalize(response)


def require_closed_payload(payload, timeout_seconds):
    if timeout_seconds != TIMEOUT_SECONDS or _payload_closed(payload) is not True:
        raise ProviderError("invalid_input")


def require_authorized_payload(payload, timeout_seconds):
    """Same closed payload. The timeout is the one bound to this execution."""
    if (type(timeout_seconds) not in (int, float) or isinstance(timeout_seconds, bool)
            or not 0 < float(timeout_seconds) <= 60 or _payload_closed(payload) is not True):
        raise ProviderError("invalid_input")


def _payload_closed(payload):
    return (type(payload) is dict and payload.get("model") == ALLOWED_MODEL
            and payload.get("store") is False and payload.get("service_tier") == "default"
            and payload.get("reasoning") == {"effort": "none"} and payload.get("stream") is False
            and payload.get("background") is False and "tools" not in payload
            and "previous_response_id" not in payload and "base_url" not in payload
            and type(payload.get("max_output_tokens")) is int
            and 16 <= payload["max_output_tokens"] <= 256)


_REQUEST_ID = re.compile(r"[A-Za-z0-9_-]{1,80}")


class DispatchGrant:
    """One pass into dispatch_authorized. A bare call does not obtain it."""

    def __init__(self):
        self._open = True

    def consume(self):
        if self._open is not True:
            return False
        self._open = False
        return True


def dispatch_authorized(client, payload, timeout_seconds, grant=None):
    """One Responses call for a release that was already spent. No retry."""
    if type(grant) is not DispatchGrant or grant.consume() is not True:
        raise ProviderError("egress_blocked")
    require_authorized_payload(payload, timeout_seconds)
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
        raise ProviderError("timeout", {"http_status": None, "usage_present": False, "cost_exact": False}) from None
    except APIStatusError as error:
        code = error.status_code if type(error.status_code) is int else None
        reason = "rate_limited" if code == 429 else "remote_unavailable"
        raise ProviderError(reason, {"http_status": code, "usage_present": False, "cost_exact": False}) from None
    except APIConnectionError:
        raise ProviderError("network_unavailable", {"usage_present": False, "cost_exact": False}) from None
    except ProviderError:
        raise
    except Exception:
        raise ProviderError("remote_unavailable") from None
    body = _normalize(response)
    request_id = getattr(response, "id", None)
    if type(request_id) is str and _REQUEST_ID.fullmatch(request_id):
        body["provider_request_id"] = request_id
    return body


def _normalize(response):
    diagnostic = _response_diagnostic(response)
    account = diagnostic.pop("_account")
    if response.model != ALLOWED_MODEL:
        raise ProviderError("model_denied", diagnostic)
    if response.status != "completed":
        raise ProviderError("incomplete_output", diagnostic)
    if type(getattr(response, "output", None)) is not list:
        raise ProviderError("invalid_output", diagnostic)
    output = []
    for item in response.output:
        if item.type != "message":
            raise ProviderError("invalid_output", diagnostic)
        content = []
        for part in item.content:
            if part.type == "refusal":
                raise ProviderError("model_refusal", diagnostic)
            if part.type != "output_text" or type(part.text) is not str:
                raise ProviderError("invalid_output", diagnostic)
            content.append({"type": "output_text", "text": part.text})
        output.append({"type": "message", "content": content})
    if account["usable"] is not True:
        raise ProviderError("consumption_ambiguous", diagnostic)
    return {
        "status": response.status, "model": response.model, "output": output,
        "usage": {
            "input_tokens": account["input_tokens"],
            "output_tokens": account["output_tokens"],
            "reasoning_tokens": account["reasoning_tokens"],
            "total_tokens": account["total_tokens"],
            "cost_exact": True,
        },
    }


def _response_diagnostic(response):
    """Status and token counts only. Provider text stays out of the exception."""
    status = getattr(response, "status", None)
    details = getattr(response, "incomplete_details", None)
    reason = getattr(details, "reason", None) if details is not None else None
    output = getattr(response, "output", None)
    account = _usage_account(getattr(response, "usage", None))
    diagnostic = {
        "finish_reason": "absent",
        "response_status": status if type(status) is str else "absent",
        "incomplete_reason": reason if type(reason) is str else "absent",
        "output_present": type(output) is list and len(output) > 0,
        "usage_present": account["usage_present"],
        "input_tokens": account["input_tokens"],
        "output_tokens": account["output_tokens"],
        "reasoning_tokens": account["reasoning_tokens"],
        "total_tokens": account["total_tokens"],
        "cost_exact": account["cost_exact"],
        "_account": account,
    }
    return diagnostic


def _usage_account(usage):
    """Keep reported counts. Absent reasoning is not zero and is not billed twice."""
    if usage is None:
        return {
            "usage_present": False, "input_tokens": None, "output_tokens": None,
            "reasoning_tokens": None, "total_tokens": None, "cost_exact": False, "usable": False,
        }
    input_kind, incoming = _read_count(getattr(usage, "input_tokens", None))
    output_kind, outgoing = _read_count(getattr(usage, "output_tokens", None))
    total_kind, total = _read_count(getattr(usage, "total_tokens", None))
    details = getattr(usage, "output_tokens_details", None)
    if details is None:
        reason_kind, reasoning = "absent", None
    else:
        reason_kind, reasoning = _read_count(getattr(details, "reasoning_tokens", None))
    invalid = "invalid" in {input_kind, output_kind, total_kind, reason_kind}
    inconsistent = False
    if invalid is not True and input_kind == "present" and output_kind == "present" and total_kind == "present":
        inconsistent = total != incoming + outgoing
    if invalid is not True and reason_kind == "present" and output_kind == "present" and reasoning > outgoing:
        inconsistent = True
    usable = invalid is not True and inconsistent is not True and input_kind == "present" and output_kind == "present"
    return {
        "usage_present": True,
        "input_tokens": incoming if input_kind == "present" else None,
        "output_tokens": outgoing if output_kind == "present" else None,
        "reasoning_tokens": reasoning if reason_kind == "present" else None,
        "total_tokens": total if total_kind == "present" else None,
        "cost_exact": usable,
        "usable": usable,
    }


def _read_count(value):
    if value is None:
        return "absent", None
    if type(value) is int and value >= 0:
        return "present", value
    return "invalid", None


def _host(url):
    return getattr(url, "host", "")


def _timeout_seconds(timeout):
    if type(timeout) is int or type(timeout) is float:
        return float(timeout)
    return float(timeout.connect)
