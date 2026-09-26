"""Clinical read for the follow-up workflow. This module is not a graph.

The tool asks FollowUpFHIRAdapter. The adapter asks a FHIRTransport.
Neither one opens HTTP or imports LangGraph.
"""

from __future__ import annotations

from langchain_core.tools import tool

from app.langgraph_fhir_client import (
    BOUNDARY_EVENTS,
    FOLLOWUP_TOOL,
    PATIENT_CASE,
    PATIENT_ID,
    FHIRTransport,
    ReadClientError,
)


MISSING_CASE = "SYN-FOLLOWUP-005"
MISSING_PATIENT_ID = "SYN-PATIENT-NOT-FOUND"
UNAVAILABLE_ANSWER = "stopped: clinical context unavailable"
CASE_PATIENT = {
    PATIENT_CASE: PATIENT_ID,
    MISSING_CASE: MISSING_PATIENT_ID,
}


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


class FollowUpFHIRAdapter:
    """Map a patient and that patient's observations. This class does not open HTTP."""

    def __init__(self, transport: FHIRTransport) -> None:
        self.transport = transport
        self.calls: list[tuple[str, str]] = []

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
        patient_id = CASE_PATIENT.get(case_id)
        if patient_id is None:
            raise ReadClientError("case has no patient")
        _mark(f"execute:{FOLLOWUP_TOOL}")
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
