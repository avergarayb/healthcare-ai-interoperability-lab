"""HTTP read client for the follow-up workflow.

This module performs GET against the configured base URL. It does not build
a graph, authorize tools, or map clinical resources.
"""

from __future__ import annotations

import logging
import os
import time

import httpx

from app.langgraph_fhir_client import BOUNDARY_EVENTS, ReadClientError


DEFAULT_BASE_URL = "http://localhost:8080/fhir"
ACCEPT = "application/fhir+json"
FHIR_READ_ATTEMPTS = 3
FHIR_RETRY_INITIAL_SECONDS = 0.25
FHIR_RETRY_MAX_SECONDS = 1.0
TRANSIENT_FHIR_STATUS = frozenset({408, 429, 500, 502, 503, 504})

log = logging.getLogger("ai-service")
_retry_sleep = time.sleep


def hapi_base_url() -> str:
    """Read the server base URL from the environment."""
    if "FHIR_BASE_URL" in os.environ:
        raw = os.environ["FHIR_BASE_URL"].strip()
    else:
        raw = DEFAULT_BASE_URL
    if not raw:
        raise ReadClientError("FHIR_BASE_URL is empty")
    return raw.rstrip("/")


class HapiReadClient:
    """GET one path from the configured server and return the JSON object."""

    def __init__(
        self,
        base_url: str | None = None,
        *,
        http_client: httpx.Client | None = None,
        timeout_seconds: float = 5.0,
    ) -> None:
        if timeout_seconds <= 0:
            raise ReadClientError("timeout must be greater than zero")
        self.base_url = hapi_base_url() if base_url is None else _normalize(base_url)
        self._http = http_client
        self._timeout = timeout_seconds
        self.calls: list[str] = []

    def get(self, path: str) -> dict:
        """GET one path. A transient failure is repeated inside this call."""
        last_error: ReadClientError | None = None
        for attempt in range(1, FHIR_READ_ATTEMPTS + 1):
            try:
                return self._read_once(path)
            except ReadClientError as exc:
                last_error = exc
                if attempt >= FHIR_READ_ATTEMPTS or not _fhir_retryable(exc):
                    raise
                log.info("fhir_read_retry status=%s attempt=%s", _fhir_status_label(exc), attempt)
                _retry_sleep(_fhir_backoff_seconds(attempt))
        if last_error is not None:
            raise last_error
        raise ReadClientError("transport failed")

    def _read_once(self, path: str) -> dict:
        BOUNDARY_EVENTS.append(f"client:{path}")
        self.calls.append(path)
        url = f"{self.base_url}/{path.lstrip('/')}"
        try:
            response = _send(self._http, url, self._timeout)
        except httpx.HTTPError as exc:
            raise ReadClientError("transport failed") from exc
        if response.status_code >= 400:
            raise ReadClientError(f"HTTP {response.status_code}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise ReadClientError("response was not JSON") from exc
        if not isinstance(payload, dict):
            raise ReadClientError("response was not a JSON object")
        return payload


def _fhir_backoff_seconds(failed_attempt: int) -> float:
    delay = FHIR_RETRY_INITIAL_SECONDS * (2 ** (failed_attempt - 1))
    return min(delay, FHIR_RETRY_MAX_SECONDS)


def _fhir_retryable(exc: ReadClientError) -> bool:
    """Retry transport loss and transient HTTP status. A missing patient is not transient."""
    text = str(exc)
    if text == "transport failed":
        return True
    if not text.startswith("HTTP "):
        return False
    code = text.removeprefix("HTTP ")
    return code.isdigit() and int(code) in TRANSIENT_FHIR_STATUS


def _fhir_status_label(exc: ReadClientError) -> str:
    text = str(exc)
    if text == "transport failed":
        return "transport"
    code = text.removeprefix("HTTP ")
    if code.isdigit():
        return code
    return "other"


def _normalize(base_url: str) -> str:
    raw = base_url.strip().rstrip("/")
    if not raw:
        raise ReadClientError("base URL is empty")
    return raw


def _send(http_client: httpx.Client | None, url: str, timeout: float) -> httpx.Response:
    headers = {"Accept": ACCEPT}
    if http_client is not None:
        return http_client.get(url, headers=headers)
    with httpx.Client(timeout=timeout) as client:
        return client.get(url, headers=headers)
