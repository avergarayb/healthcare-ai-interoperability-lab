"""HTTP read client for the follow-up workflow.

This module performs GET against the configured base URL. It does not build
a graph, authorize tools, or map clinical resources.
"""

from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl, unquote, urljoin, urlsplit, urlunsplit

import httpx

from app.langgraph_fhir_client import (
    BOUNDARY_EVENTS,
    BoundedSearchResult,
    BoundedSearchStatus,
    FHIR_NEXT_URL_MAX_LENGTH,
    FHIR_SEARCH_MAX_PAGES,
    FHIR_SEARCH_MAX_UNIQUE_RESOURCES_PER_TYPE,
    ReadClientError,
    bundle_list_field,
)


DEFAULT_BASE_URL = "http://localhost:8080/fhir"
ACCEPT = "application/fhir+json"
FHIR_READ_ATTEMPTS = 3
FHIR_RETRY_INITIAL_SECONDS = 0.25
FHIR_RETRY_MAX_SECONDS = 1.0
TRANSIENT_FHIR_STATUS = frozenset({408, 429, 500, 502, 503, 504})
_ENCODED_SEPARATOR = re.compile(r"%(?:2f|5c)", re.IGNORECASE)
_PERCENT_ESCAPE = re.compile(r"%([0-9a-fA-F]{2})")
_INVALID_PERCENT_ESCAPE = re.compile(r"%(?![0-9a-fA-F]{2})")
_UNRESERVED = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~")
_HAPI_CONTINUATION_KEYS = frozenset(
    {"_getpages", "_getpagesoffset", "_count", "_pretty", "_bundletype"}
)
_HAPI_REQUIRED_KEYS = frozenset({"_getpages", "_getpagesoffset", "_count", "_bundletype"})
_HAPI_PAGE_TOKEN_MAX_LENGTH = 512

log = logging.getLogger("ai-service")
_retry_sleep = time.sleep


@dataclass
class _SearchTraversal:
    resource_type: str
    page_size: int
    hapi_token: str | None = None
    hapi_offset: int = 0


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
        self.base_url = _normalize(hapi_base_url() if base_url is None else base_url)
        self._http = http_client
        self._timeout = timeout_seconds
        self.calls: list[str] = []

    def get(self, path: str) -> dict:
        """GET one path. A transient failure is repeated inside this call."""
        url = f"{self.base_url}/{path.lstrip('/')}"
        return self._get_url(url, path)

    def _get_url(self, url: str, call_label: str) -> dict:
        """GET one already-authorized URL with the existing per-page retry."""
        last_error: ReadClientError | None = None
        for attempt in range(1, FHIR_READ_ATTEMPTS + 1):
            try:
                return self._read_once(url, call_label)
            except ReadClientError as exc:
                last_error = exc
                if attempt >= FHIR_READ_ATTEMPTS or not _fhir_retryable(exc):
                    raise
                log.info("fhir_read_retry status=%s attempt=%s", _fhir_status_label(exc), attempt)
                _retry_sleep(_fhir_backoff_seconds(attempt))
        if last_error is not None:
            raise last_error
        raise ReadClientError("transport failed")

    def _read_once(self, url: str, call_label: str) -> dict:
        BOUNDARY_EVENTS.append(f"client:{call_label}")
        self.calls.append(call_label)
        try:
            response = _send(self._http, url, self._timeout)
        except httpx.HTTPError as exc:
            raise ReadClientError("transport failed") from exc
        if 300 <= response.status_code < 400:
            raise ReadClientError("redirect response is not allowed")
        if response.status_code >= 400:
            raise ReadClientError(f"HTTP {response.status_code}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise ReadClientError("response was not JSON") from exc
        if not isinstance(payload, dict):
            raise ReadClientError("response was not a JSON object")
        return payload

    def search(self, path: str, expected_resource_type: str) -> BoundedSearchResult:
        """Traverse one fixed FHIR search endpoint within strict V1 bounds."""
        current_url = f"{self.base_url}/{path.lstrip('/')}"
        try:
            page_size = _validate_initial_search_url(
                self.base_url,
                current_url,
                expected_resource_type,
            )
        except ReadClientError as exc:
            return BoundedSearchResult(BoundedSearchStatus.FAILED, (), str(exc))
        traversal = _SearchTraversal(expected_resource_type, page_size)
        visited = {_canonical_url(current_url)}
        resources: list[dict] = []
        by_identity: dict[tuple[str, str], dict] = {}
        resource_limit_hit = False
        page_number = 0
        while True:
            page_number += 1
            label = (
                path
                if page_number == 1
                else f"{expected_resource_type}:continuation:{page_number}"
            )
            try:
                bundle = self._get_url(current_url, label)
                page_resources, next_link = _search_page(bundle, expected_resource_type)
                for resource in page_resources:
                    resource_id = resource.get("id")
                    if not isinstance(resource_id, str) or not resource_id:
                        raise ReadClientError("search resource has no id")
                    identity = (expected_resource_type, resource_id)
                    prior = by_identity.get(identity)
                    if prior is not None:
                        if prior != resource:
                            raise ReadClientError("conflicting duplicate search resource")
                        continue
                    if len(by_identity) >= FHIR_SEARCH_MAX_UNIQUE_RESOURCES_PER_TYPE:
                        resource_limit_hit = True
                        continue
                    copied = dict(resource)
                    by_identity[identity] = copied
                    resources.append(copied)
                next_url: str | None = None
                if next_link is not None:
                    next_url = _validated_next_url(
                        self.base_url,
                        current_url,
                        next_link,
                        traversal,
                    )
                    canonical = _canonical_url(next_url)
                    if canonical in visited:
                        raise ReadClientError("cyclic search continuation")
                if resource_limit_hit or (
                    next_url is not None
                    and len(by_identity) >= FHIR_SEARCH_MAX_UNIQUE_RESOURCES_PER_TYPE
                ):
                    return BoundedSearchResult(
                        BoundedSearchStatus.INCOMPLETE_LIMIT,
                        tuple(resources),
                        "unique resource limit reached",
                    )
                if next_url is None:
                    return BoundedSearchResult(BoundedSearchStatus.COMPLETE, tuple(resources))
                if page_number >= FHIR_SEARCH_MAX_PAGES:
                    return BoundedSearchResult(
                        BoundedSearchStatus.INCOMPLETE_LIMIT,
                        tuple(resources),
                        "page limit reached with continuation",
                    )
                visited.add(canonical)
                current_url = next_url
            except ReadClientError as exc:
                return BoundedSearchResult(BoundedSearchStatus.FAILED, tuple(resources), str(exc))


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
    try:
        parsed = urlsplit(raw)
    except ValueError as exc:
        raise ReadClientError("base URL is not a safe HTTP origin") from exc
    if (
        parsed.scheme.lower() not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ReadClientError("base URL is not a safe HTTP origin")
    return raw


def _send(http_client: httpx.Client | None, url: str, timeout: float) -> httpx.Response:
    headers = {"Accept": ACCEPT}
    if http_client is not None:
        return http_client.get(url, headers=headers, follow_redirects=False)
    with httpx.Client(timeout=timeout, follow_redirects=False) as client:
        return client.get(url, headers=headers)


def _search_page(bundle: dict, expected_resource_type: str) -> tuple[list[dict], str | None]:
    if bundle.get("resourceType") != "Bundle" or bundle.get("type") != "searchset":
        raise ReadClientError("search response must be a searchset bundle")
    entries = bundle_list_field(bundle, "entry", "search bundle entries must be a list")
    resources: list[dict] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ReadClientError("bundle entry must be an object")
        resource = entry.get("resource")
        if not isinstance(resource, dict) or resource.get("resourceType") != expected_resource_type:
            raise ReadClientError(f"bundle entry must contain {expected_resource_type}")
        resources.append(dict(resource))
    links = bundle_list_field(bundle, "link", "bundle links must be a list")
    next_urls: list[str] = []
    for link in links:
        if not isinstance(link, dict):
            raise ReadClientError("bundle link must be an object")
        if link.get("relation") != "next":
            continue
        url = link.get("url")
        if not isinstance(url, str) or not url.strip():
            raise ReadClientError("next link must contain a non-empty URL")
        next_urls.append(url.strip())
    if len(next_urls) > 1:
        raise ReadClientError("bundle contains multiple next links")
    return resources, next_urls[0] if next_urls else None


def _validate_initial_search_url(base_url: str, url: str, resource_type: str) -> int:
    parsed_base = urlsplit(base_url)
    parsed = urlsplit(url)
    if not parsed.query:
        raise ReadClientError("FHIR search requires a fixed query")
    _validate_common_target(parsed_base, parsed)
    _validate_resource_search_target(parsed_base, parsed, resource_type)
    pairs = _parse_query(parsed.query)
    counts = [value for key, value in pairs if key == "_count"]
    if len(counts) != 1 or not _ascii_decimal(counts[0]) or int(counts[0]) <= 0:
        raise ReadClientError("FHIR search requires one positive page size")
    return int(counts[0])


def _validated_next_url(
    base_url: str,
    current_url: str,
    raw: str,
    traversal: _SearchTraversal,
) -> str:
    if len(raw) > FHIR_NEXT_URL_MAX_LENGTH:
        raise ReadClientError("next link exceeds maximum length")
    if _INVALID_PERCENT_ESCAPE.search(raw) or any(
        ord(character) < 32 or ord(character) == 127 for character in raw
    ):
        raise ReadClientError("next link is malformed")
    try:
        raw_path = urlsplit(raw).path
        resolved = urljoin(current_url, raw)
    except ValueError as exc:
        raise ReadClientError("next link is malformed") from exc
    if _ENCODED_SEPARATOR.search(raw_path) or "\\" in raw_path:
        raise ReadClientError("next link contains an encoded or invalid path separator")
    if len(resolved) > FHIR_NEXT_URL_MAX_LENGTH:
        raise ReadClientError("resolved next link exceeds maximum length")
    parsed_base = urlsplit(base_url)
    parsed = urlsplit(resolved)
    _validate_common_target(parsed_base, parsed)
    expected_path = f"{parsed_base.path.rstrip('/')}/{traversal.resource_type}"
    if parsed.path == expected_path:
        if traversal.hapi_token is not None:
            raise ReadClientError("FHIR continuation shape changed during traversal")
        _validate_resource_search_target(parsed_base, parsed, traversal.resource_type)
        if any(key == "_getpages" for key, _value in _parse_query(parsed.query)):
            raise ReadClientError("HAPI continuation must use the FHIR base endpoint")
    elif parsed.path == parsed_base.path:
        _validate_hapi_continuation(parsed, traversal)
    else:
        raise ReadClientError("FHIR continuation endpoint does not match the search")
    return resolved


def _validate_common_target(base, target) -> None:
    if target.username is not None or target.password is not None:
        raise ReadClientError("FHIR continuation credentials are not allowed")
    if target.fragment:
        raise ReadClientError("FHIR continuation fragments are not allowed")
    if target.scheme.lower() != base.scheme.lower() or (target.hostname or "").lower() != (
        base.hostname or ""
    ).lower():
        raise ReadClientError("FHIR continuation origin does not match")
    if _effective_port(target) != _effective_port(base):
        raise ReadClientError("FHIR continuation port does not match")
    raw_segments = target.path.split("/")
    decoded_segments = [unquote(segment) for segment in raw_segments]
    if any(segment in {".", ".."} for segment in decoded_segments):
        raise ReadClientError("FHIR continuation path traversal is not allowed")
    if _ENCODED_SEPARATOR.search(target.path) or "\\" in target.path:
        raise ReadClientError("FHIR continuation contains an invalid path separator")


def _validate_resource_search_target(base, target, resource_type: str) -> None:
    expected_path = f"{base.path.rstrip('/')}/{resource_type}"
    if target.path != expected_path:
        raise ReadClientError("FHIR continuation endpoint does not match the search")
    if not target.query:
        raise ReadClientError("FHIR continuation must remain a search URL")


def _validate_hapi_continuation(target, traversal: _SearchTraversal) -> None:
    pairs = _parse_query(target.query)
    keys = [key for key, _value in pairs]
    if len(keys) != len(set(keys)):
        raise ReadClientError("HAPI continuation query contains duplicate parameters")
    key_set = set(keys)
    if not _HAPI_REQUIRED_KEYS.issubset(key_set) or not key_set.issubset(
        _HAPI_CONTINUATION_KEYS
    ):
        raise ReadClientError("HAPI continuation query parameters are not allowed")
    values = dict(pairs)
    token = values["_getpages"]
    if not token or len(token) > _HAPI_PAGE_TOKEN_MAX_LENGTH:
        raise ReadClientError("HAPI continuation token is invalid")
    offset_text = values["_getpagesoffset"]
    count_text = values["_count"]
    if not _ascii_decimal(offset_text):
        raise ReadClientError("HAPI continuation offset is invalid")
    if not _ascii_decimal(count_text) or int(count_text) != traversal.page_size:
        raise ReadClientError("HAPI continuation page size changed")
    if values["_bundletype"] != "searchset":
        raise ReadClientError("HAPI continuation bundle type is invalid")
    if "_pretty" in values and values["_pretty"] != "true":
        raise ReadClientError("HAPI continuation pretty value is invalid")
    expected_offset = traversal.hapi_offset + traversal.page_size
    offset = int(offset_text)
    if offset != expected_offset:
        raise ReadClientError("HAPI continuation offset is inconsistent")
    if traversal.hapi_token is not None and token != traversal.hapi_token:
        raise ReadClientError("HAPI continuation token changed")
    if traversal.hapi_token is None:
        traversal.hapi_token = token
    traversal.hapi_offset = offset


def _parse_query(query: str) -> list[tuple[str, str]]:
    if not query:
        raise ReadClientError("FHIR continuation must remain a search URL")
    try:
        return parse_qsl(query, keep_blank_values=True, strict_parsing=True)
    except ValueError as exc:
        raise ReadClientError("FHIR continuation query is malformed") from exc


def _ascii_decimal(value: str) -> bool:
    return bool(value) and value.isascii() and value.isdigit()


def _effective_port(parsed) -> int:
    try:
        port = parsed.port
    except ValueError as exc:
        raise ReadClientError("FHIR URL has an invalid port") from exc
    if port is not None:
        return port
    return 443 if parsed.scheme.lower() == "https" else 80


def _canonical_url(url: str) -> str:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()
    authority_host = f"[{host}]" if ":" in host else host
    default_port = 443 if parsed.scheme.lower() == "https" else 80
    port = _effective_port(parsed)
    authority = authority_host if port == default_port else f"{authority_host}:{port}"
    path = _normalize_percent_escapes(parsed.path)
    query = _normalize_percent_escapes(parsed.query)
    return urlunsplit((parsed.scheme.lower(), authority, path, query, ""))


def _normalize_percent_escapes(value: str) -> str:
    def replacement(match: re.Match[str]) -> str:
        character = chr(int(match.group(1), 16))
        return character if character in _UNRESERVED else f"%{match.group(1).upper()}"

    return _PERCENT_ESCAPE.sub(replacement, value)
