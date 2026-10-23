"""HTTP client for Java Clinical Federation v1.

The response is a federation envelope of FHIR R4 resources, not a FHIR Bundle.
This module does not call Mini HIS, Mini LIS, or HAPI.
"""

from __future__ import annotations

import logging
import re
from uuid import uuid4

import httpx

from app.config import Settings


log = logging.getLogger("ai-service")

CONTRACT_VERSION = "clinical-federation-v1"
FEDERATION_PATH = "/api/clinical-federation/v1/context"
RESOURCE_TYPES = (
    "Patient",
    "Encounter",
    "Observation",
    "Appointment",
    "ServiceRequest",
    "DiagnosticReport",
)
_KEY = re.compile(r"[a-z0-9\-]{1,64}")
_ID = re.compile(r"[A-Za-z0-9\-.]{1,64}")
_SYSTEM = re.compile(r"https://[A-Za-z0-9./_\-]{1,200}")
_STATUSES = frozenset({"complete", "partial", "failed"})


class FederationClientError(Exception):
    """Stable failure. The message is a code and contains no clinical payload."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class ClinicalFederationClient:
    """POST one authorized federation query. Sources come from settings, not from a prompt."""

    def __init__(
        self,
        base_url: str,
        service_token: str,
        *,
        organization_id: str,
        patient_system_key: str,
        patient_identifier_system: str,
        sources: tuple[str, ...],
        timeout_seconds: float = 20.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        if timeout_seconds <= 0:
            raise FederationClientError("federation_unconfigured")
        normalized = base_url.strip().rstrip("/")
        if (
            not normalized
            or not service_token.strip()
            or not _ID.fullmatch(organization_id)
            or not _KEY.fullmatch(patient_system_key)
            or not _SYSTEM.fullmatch(patient_identifier_system)
            or not sources
            or any(_KEY.fullmatch(source) is None for source in sources)
        ):
            raise FederationClientError("federation_unconfigured")
        self.base_url = normalized
        self._token = service_token.strip()
        self.organization_id = organization_id
        self.patient_system_key = patient_system_key
        self.patient_identifier_system = patient_identifier_system
        self.sources = sources
        self._timeout = timeout_seconds
        self._http = http_client

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        *,
        http_client: httpx.Client | None = None,
    ) -> ClinicalFederationClient:
        return cls(
            settings.model_boundary_base_url,
            settings.federation_participant_token,
            organization_id=settings.federation_requesting_organization_id,
            patient_system_key=settings.federation_patient_system_key,
            patient_identifier_system=settings.federation_patient_identifier_system,
            sources=tuple(settings.federation_sources),
            timeout_seconds=settings.federation_timeout_seconds,
            http_client=http_client,
        )

    def query(self, identifier_value: str) -> dict:
        if _ID.fullmatch(identifier_value) is None:
            raise FederationClientError("federation_invalid_identity")
        correlation_id = "FED-" + uuid4().hex[:16].upper()
        body = {
            "requestingOrganizationId": self.organization_id,
            "patient": {
                "systemKey": self.patient_system_key,
                "identifierSystem": self.patient_identifier_system,
                "identifierValue": identifier_value,
            },
            "sources": list(self.sources),
            "resourceTypes": list(RESOURCE_TYPES),
            "correlationId": correlation_id,
        }
        close_client = self._http is None
        http = self._http or httpx.Client(timeout=self._timeout, follow_redirects=False)
        try:
            try:
                response = http.post(
                    f"{self.base_url}{FEDERATION_PATH}",
                    json=body,
                    headers={
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                        "X-Service-Token": self._token,
                    },
                    timeout=self._timeout,
                )
            except httpx.TimeoutException as exc:
                raise FederationClientError("federation_timeout") from exc
            except httpx.HTTPError as exc:
                raise FederationClientError("federation_unavailable") from exc
        finally:
            if close_client:
                http.close()
        if response.status_code == 401:
            raise FederationClientError("federation_unauthenticated")
        if response.status_code == 403:
            raise FederationClientError("federation_unauthorized")
        if response.status_code == 400:
            raise FederationClientError("federation_rejected")
        if response.status_code != 200:
            raise FederationClientError("federation_unavailable")
        try:
            parsed = response.json()
        except ValueError as exc:
            raise FederationClientError("federation_unavailable") from exc
        if not isinstance(parsed, dict) or parsed.get("contractVersion") != CONTRACT_VERSION:
            raise FederationClientError("federation_unavailable")
        if parsed.get("status") not in _STATUSES or not isinstance(parsed.get("sources"), list):
            raise FederationClientError("federation_unavailable")
        if not isinstance(parsed.get("entries"), list):
            raise FederationClientError("federation_unavailable")
        log.info(
            "federation_query correlation=%s status=%s sources=%s",
            parsed.get("correlationId") or correlation_id,
            parsed.get("status"),
            len(parsed["sources"]),
        )
        return parsed
