"""Clinical read for the follow-up workflow. This module is not a graph.

The tool asks FollowUpFHIRAdapter. The adapter asks a FHIRTransport.
Neither one opens HTTP or imports LangGraph.

A case id is an application identifier. It is stored on Patient.identifier
with system https://lab.local/followup-case. It is not Patient.id.
"""

from __future__ import annotations

from urllib.parse import quote

from langchain_core.tools import tool

from app.langgraph_fhir_client import (
    BOUNDARY_EVENTS,
    CASE_IDENTIFIER_SYSTEM,
    FOLLOWUP_TOOL,
    FHIRTransport,
    ReadClientError,
)


UNAVAILABLE_ANSWER = "stopped: clinical context unavailable"


def _mark(event: str) -> None:
    BOUNDARY_EVENTS.append(event)


def _name_text(payload: dict) -> str | None:
    names = payload.get("name")
    if not isinstance(names, list):
        return None
    for entry in names:
        if not isinstance(entry, dict):
            continue
        text = entry.get("text")
        if isinstance(text, str) and text.strip():
            return text.strip()
        given = entry.get("given") if isinstance(entry.get("given"), list) else []
        family = entry.get("family") if isinstance(entry.get("family"), str) else ""
        parts = [part.strip() for part in given if isinstance(part, str) and part.strip()]
        if family.strip():
            parts.append(family.strip())
        if parts:
            return " ".join(parts)
    return None


def _observations_from_bundle(payload: dict) -> list[dict]:
    if payload.get("resourceType") != "Bundle":
        raise ReadClientError("observation response must be a bundle")
    entries = payload.get("entry")
    if not isinstance(entries, list) or not entries:
        raise ReadClientError("observation bundle has no entries")
    observations: list[dict] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ReadClientError("bundle entry must be an object")
        resource = entry.get("resource")
        if not isinstance(resource, dict) or resource.get("resourceType") != "Observation":
            raise ReadClientError("bundle entry must contain an observation")
        observations.append(dict(resource))
    return observations


def case_search_path(case_id: str) -> str:
    """Search Patient by identifier. The case id is the identifier value, not Patient.id."""
    token = quote(f"{CASE_IDENTIFIER_SYSTEM}|{case_id}", safe="")
    return f"Patient?identifier={token}"


def _case_identifier_matches(patient: dict, case_id: str) -> bool:
    identifiers = patient.get("identifier")
    if not isinstance(identifiers, list):
        return False
    return any(
        isinstance(item, dict)
        and item.get("system") == CASE_IDENTIFIER_SYSTEM
        and item.get("value") == case_id
        for item in identifiers
    )


def _patient_id_from_case_search(payload: dict, case_id: str) -> str:
    if payload.get("resourceType") != "Bundle":
        raise ReadClientError("case search must be a bundle")
    entries = payload.get("entry") or []
    if not isinstance(entries, list):
        raise ReadClientError("case search entries must be a list")
    matches: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        resource = entry.get("resource")
        if not isinstance(resource, dict) or resource.get("resourceType") != "Patient":
            continue
        if not _case_identifier_matches(resource, case_id):
            continue
        patient_id = resource.get("id")
        if not isinstance(patient_id, str) or not patient_id:
            raise ReadClientError("matched patient has no id")
        matches.append(patient_id)
    if not matches:
        raise ReadClientError("case has no patient")
    if len(matches) != 1:
        raise ReadClientError("case matched more than one patient")
    return matches[0]


class FollowUpFHIRAdapter:
    """Map a patient and that patient's observations. This class does not open HTTP."""

    def __init__(self, transport: FHIRTransport) -> None:
        self.transport = transport
        self.calls: list[tuple[str, str]] = []

    def patient_id_for_case(self, case_id: str) -> str:
        """Resolve one case through Patient.identifier. This does not read Patient/{case_id}."""
        _mark("adapter:patient_for_case")
        self.calls.append(("patient_for_case", case_id))
        payload = self.transport.get(case_search_path(case_id))
        return _patient_id_from_case_search(payload, case_id)

    def get_patient(self, patient_id: str) -> dict[str, str]:
        _mark("adapter:get_patient")
        self.calls.append(("get_patient", patient_id))
        payload = self.transport.get(f"Patient/{patient_id}")
        if payload.get("resourceType") != "Patient" or payload.get("id") != patient_id:
            raise ReadClientError("patient response did not match")
        patient = {"resourceType": "Patient", "id": str(payload["id"])}
        name = _name_text(payload)
        if name is not None:
            patient["name"] = name
        return patient

    def get_observations(self, patient_id: str) -> list[dict]:
        _mark("adapter:get_observations")
        self.calls.append(("get_observations", patient_id))
        payload = self.transport.get(f"Observation?subject=Patient/{patient_id}")
        observations = _observations_from_bundle(payload)
        for resource in observations:
            if not isinstance(resource.get("id"), str) or not resource.get("id"):
                raise ReadClientError("observation has no id")
        return observations


def make_followup_tool(adapter: FollowUpFHIRAdapter):
    """Build the follow-up read. The tool sees the adapter and the case id."""

    @tool
    def get_patient_followup_context(case_id: str) -> dict[str, object]:
        """Read one case through the adapter."""
        _mark(f"execute:{FOLLOWUP_TOOL}")
        patient_id = adapter.patient_id_for_case(case_id)
        return {
            "patient": adapter.get_patient(patient_id),
            "observations": adapter.get_observations(patient_id),
        }

    return get_patient_followup_context


def _resource_refs(patient: dict, observations: list[dict]) -> list[str]:
    patient_id = patient.get("id")
    if not isinstance(patient_id, str) or not patient_id:
        raise ReadClientError("patient has no id")
    refs = [f"Patient/{patient_id}"]
    for resource in observations:
        observation_id = resource.get("id")
        if not isinstance(observation_id, str) or not observation_id:
            raise ReadClientError("observation has no id")
        refs.append(f"Observation/{observation_id}")
    return refs
