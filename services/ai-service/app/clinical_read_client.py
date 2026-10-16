"""HTTP client for Healthcare Interoperability clinical read contract v1.

This module speaks GET /api/clinical-read/v1. It does not import Java types
and it does not call HAPI.
"""

from __future__ import annotations

from urllib.parse import parse_qsl, quote, urlsplit

import httpx

from app.config import Settings
from app.langgraph_fhir_client import (
    BoundedSearchResult,
    BoundedSearchStatus,
    ExactResourceNotFound,
    ReadClientError,
)


CONTRACT_VERSION = "clinical-read-v1"
CLINICAL_READ_PREFIX = "/api/clinical-read/v1"
_UNAVAILABLE = "clinical read unavailable"
_EXACT_COLLECTIONS = {
    "Patient": "patients",
    "Encounter": "encounters",
    "Observation": "observations",
}


class ClinicalReadClient:
    """Translate the versioned Java read contract into the follow-up read client."""

    def __init__(
        self,
        base_url: str,
        service_token: str,
        *,
        timeout_seconds: float = 5.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        if timeout_seconds <= 0:
            raise ReadClientError("timeout must be greater than zero")
        normalized = base_url.strip().rstrip("/")
        if not normalized:
            raise ReadClientError("clinical read base URL is empty")
        self.base_url = normalized
        self._token = service_token.strip()
        self._timeout = timeout_seconds
        self._http = http_client

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        *,
        http_client: httpx.Client | None = None,
    ) -> ClinicalReadClient:
        return cls(
            settings.model_boundary_base_url,
            settings.model_boundary_service_token,
            timeout_seconds=settings.model_boundary_timeout_seconds,
            http_client=http_client,
        )

    def get(self, path: str) -> dict:
        resource, query = _split_path(path)
        resource_type, separator, logical_id = resource.partition("/")
        collection = _EXACT_COLLECTIONS.get(resource_type)
        if query or separator != "/" or collection is None or not logical_id or "/" in logical_id:
            raise ReadClientError("clinical read path is not authorized")
        status, body = self._exchange(
            f"{self.base_url}{CLINICAL_READ_PREFIX}/{collection}/{quote(logical_id, safe='')}",
            None,
        )
        if status == 404 and isinstance(body, dict) and body.get("error") == "not_found":
            raise ExactResourceNotFound()
        if status != 200 or not isinstance(body, dict):
            raise ReadClientError(_UNAVAILABLE)
        return _exact_resource(body, resource_type, logical_id)

    def search(self, path: str, expected_resource_type: str) -> BoundedSearchResult:
        try:
            return self._search(path, expected_resource_type)
        except ReadClientError as exc:
            return BoundedSearchResult(BoundedSearchStatus.FAILED, (), str(exc))

    def _search(self, path: str, expected_resource_type: str) -> BoundedSearchResult:
        resource, query = _split_path(path)
        if expected_resource_type == "Patient" and resource == "Patient":
            system, value = _identifier_token(query.get("identifier"))
            status, body = self._exchange(
                f"{self.base_url}{CLINICAL_READ_PREFIX}/patients",
                {"identifierSystem": system, "identifierValue": value},
            )
        elif expected_resource_type == "Appointment" and resource == "Appointment":
            patient_id = _patient_logical_id(query.get("patient"))
            _known_query(query, {"patient", "_count"})
            status, body = self._exchange(
                f"{self.base_url}{CLINICAL_READ_PREFIX}/appointments",
                {"patient": patient_id},
            )
        elif expected_resource_type == "Encounter" and resource == "Encounter":
            _known_query(query, {"patient", "status", "_count"})
            status, body = self._exchange(
                f"{self.base_url}{CLINICAL_READ_PREFIX}/encounters",
                {"patient": _patient_logical_id(query.get("patient")), "status": _required_status(query.get("status"))},
            )
        elif expected_resource_type == "Observation" and resource == "Observation":
            _known_query(query, {"patient", "subject", "status", "_count"})
            status, body = self._exchange(
                f"{self.base_url}{CLINICAL_READ_PREFIX}/observations",
                {
                    "patient": _one_patient_reference(query.get("patient"), query.get("subject")),
                    "status": _required_status(query.get("status")),
                },
            )
        else:
            raise ReadClientError("clinical read path is not authorized")
        if status != 200 or not isinstance(body, dict):
            raise ReadClientError(_UNAVAILABLE)
        return _collection(body, expected_resource_type)

    def _exchange(self, url: str, params: dict[str, str] | None) -> tuple[int, dict | None]:
        if not self._token:
            raise ReadClientError(_UNAVAILABLE)
        headers = {"Accept": "application/json", "X-Service-Token": self._token}
        close_client = self._http is None
        http = self._http or httpx.Client(timeout=self._timeout, follow_redirects=False)
        try:
            response = http.get(url, params=params, headers=headers, timeout=self._timeout)
        except httpx.HTTPError as exc:
            raise ReadClientError(_UNAVAILABLE) from exc
        finally:
            if close_client:
                http.close()
        if not response.content:
            return response.status_code, None
        try:
            parsed = response.json()
        except ValueError as exc:
            raise ReadClientError(_UNAVAILABLE) from exc
        if not isinstance(parsed, dict):
            raise ReadClientError(_UNAVAILABLE)
        return response.status_code, parsed


def _split_path(path: str) -> tuple[str, dict[str, str]]:
    if not isinstance(path, str) or not path or "://" in path:
        raise ReadClientError("clinical read path is not authorized")
    parsed = urlsplit(path)
    if parsed.scheme or parsed.netloc:
        raise ReadClientError("clinical read path is not authorized")
    pairs = parse_qsl(parsed.query, keep_blank_values=False)
    if len(pairs) != len({key for key, _value in pairs}):
        raise ReadClientError("clinical read path is not authorized")
    return parsed.path.strip("/"), dict(pairs)


def _identifier_token(raw: object) -> tuple[str, str]:
    if not isinstance(raw, str) or raw.count("|") != 1:
        raise ReadClientError("clinical read path is not authorized")
    system, value = raw.split("|", 1)
    if not system.strip() or not value.strip():
        raise ReadClientError("clinical read path is not authorized")
    return system, value


def _known_query(query: dict[str, str], allowed: set[str]) -> None:
    if any(key not in allowed for key in query):
        raise ReadClientError("clinical read path is not authorized")


def _required_status(raw: object) -> str:
    if not isinstance(raw, str) or not raw or "/" in raw:
        raise ReadClientError("clinical read path is not authorized")
    return raw


def _one_patient_reference(patient: object, subject: object) -> str:
    if (patient is None) == (subject is None):
        raise ReadClientError("clinical read path is not authorized")
    return _patient_logical_id(patient if patient is not None else subject)


def _patient_logical_id(raw: object) -> str:
    if not isinstance(raw, str) or not raw:
        raise ReadClientError("clinical read path is not authorized")
    logical_id = raw.removeprefix("Patient/") if raw.startswith("Patient/") else raw
    if not logical_id or "/" in logical_id:
        raise ReadClientError("clinical read path is not authorized")
    return logical_id


def _exact_resource(body: dict, resource_type: str, logical_id: str) -> dict:
    if body.get("contractVersion") != CONTRACT_VERSION:
        raise ReadClientError(_UNAVAILABLE)
    resource = body.get("resource")
    if (
        not isinstance(resource, dict)
        or resource.get("resourceType") != resource_type
        or resource.get("id") != logical_id
    ):
        raise ReadClientError(_UNAVAILABLE)
    return dict(resource)


def _collection(body: dict, expected_resource_type: str) -> BoundedSearchResult:
    if body.get("contractVersion") != CONTRACT_VERSION or body.get("resourceType") != expected_resource_type:
        raise ReadClientError(_UNAVAILABLE)
    resources = body.get("resources")
    if not isinstance(resources, list) or any(not isinstance(item, dict) for item in resources):
        raise ReadClientError(_UNAVAILABLE)
    if any(item.get("resourceType") != expected_resource_type for item in resources):
        raise ReadClientError(_UNAVAILABLE)
    copied = tuple(dict(item) for item in resources)
    status = body.get("collectionStatus")
    if status == "complete":
        return BoundedSearchResult(BoundedSearchStatus.COMPLETE, copied)
    if status == "incomplete":
        return BoundedSearchResult(BoundedSearchStatus.INCOMPLETE_LIMIT, copied)
    raise ReadClientError(_UNAVAILABLE)
