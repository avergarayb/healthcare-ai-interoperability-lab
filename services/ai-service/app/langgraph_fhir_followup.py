"""Clinical read for the follow-up workflow. This module is not a graph.

The tool asks FollowUpFHIRAdapter. The adapter asks a FHIRTransport.
Neither one opens HTTP or imports LangGraph.

A case id is an application identifier. It is stored on Patient.identifier
with system https://lab.local/followup-case. It is not Patient.id.
"""

from __future__ import annotations

import contextvars
import re
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from urllib.parse import quote

from langchain_core.tools import tool

from app.langgraph_fhir_client import (
    APPOINTMENTS_TOOL,
    BOUNDARY_EVENTS,
    CASE_IDENTIFIER_SYSTEM,
    FOLLOWUP_TOOL,
    FHIRTransport,
    ReadClientError,
)


UNAVAILABLE_ANSWER = "stopped: clinical context unavailable"
_PATIENT_ID_TOKEN = re.compile(r"[A-Za-z0-9\-]+")
UPCOMING_CONFIRMED = "UPCOMING_CONFIRMED"
UPCOMING_UNCONFIRMED = "UPCOMING_UNCONFIRMED"
CANCELLED = "CANCELLED"
PAST = "PAST"
NONE = "NONE"
OTHER = "OTHER"
_UNCONFIRMED_STATUS = frozenset({"pending", "proposed"})
_PAST_STATUS = frozenset({"booked", "fulfilled"})
_CLASS_ORDER = (UPCOMING_CONFIRMED, UPCOMING_UNCONFIRMED, CANCELLED, PAST, OTHER)


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
    """Read Observation entries. A valid bundle with no entries is an empty result."""
    if payload.get("resourceType") != "Bundle":
        raise ReadClientError("observation response must be a bundle")
    entries = payload.get("entry") or []
    if not isinstance(entries, list):
        raise ReadClientError("observation bundle entries must be a list")
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


class FollowUpReadLedger:
    """Provenance for one run. A status is never inferred from a missing list."""

    def __init__(self) -> None:
        self.patient = "not_read"
        self.observation = "not_read"
        self.patient_resource: dict | None = None
        self.observations: list[dict] | None = None
        self.schedule_check = "not_checked"
        self.classifications: tuple[str, ...] = ()
        self.appointments: tuple[tuple[str, str], ...] = ()


class _ReadScope:
    """Clinical reads and authorization state for one invoke."""

    def __init__(self, case_id: str) -> None:
        self.case_id = case_id
        self.ledger = FollowUpReadLedger()
        self.policy_status = ""
        self.policy_reason = ""


_READ_SCOPE: contextvars.ContextVar[_ReadScope | None] = contextvars.ContextVar(
    "followup_read_scope",
    default=None,
)


class FollowUpFHIRAdapter:
    """Map a patient and that patient's observations. This class does not open HTTP."""

    def __init__(self, transport: FHIRTransport, now: Callable[[], datetime] | None = None) -> None:
        self.transport = transport
        self.calls: list[tuple[str, str]] = []
        self._now = now or (lambda: datetime.now(timezone.utc))

    @property
    def ledger(self) -> FollowUpReadLedger:
        return self._scope().ledger

    def _scope(self) -> _ReadScope:
        scope = _READ_SCOPE.get()
        if scope is None:
            raise RuntimeError("follow-up read is not bound to a run")
        return scope

    def record_policy_decision(self, status: str, reason: str) -> None:
        """Keep one routing verdict in the same scope as this run's reads."""
        scope = self._scope()
        scope.policy_status = status
        scope.policy_reason = reason

    def policy_decision(self) -> tuple[str, str]:
        """Return only the routing verdict owned by the current invoke."""
        scope = self._scope()
        return scope.policy_status, scope.policy_reason

    @contextmanager
    def bind_read(self, case_id: str) -> Iterator[None]:
        """Bind this execution's case and a new ledger. Tool threads copy this context."""
        token = _READ_SCOPE.set(_ReadScope(case_id))
        try:
            yield
        finally:
            _READ_SCOPE.reset(token)

    def record_patient_search_failure(self, exc: ReadClientError) -> None:
        """A context search ended without a Patient resource. A resolved Patient stays."""
        if self.ledger.patient == "resolved":
            return
        if str(exc) == "case has no patient":
            self.ledger.patient = "not_resolved"
            return
        self.ledger.patient = "unavailable"

    def record_patient_read_failure(self) -> None:
        if self.ledger.patient != "resolved":
            self.ledger.patient = "unavailable"

    def record_patient_resolved(self, patient: dict) -> None:
        self.ledger.patient = "resolved"
        self.ledger.patient_resource = dict(patient)

    def record_observation_failure(self) -> None:
        if self.ledger.observation == "not_read":
            self.ledger.observation = "unavailable"

    def record_observations(self, observations: list[dict]) -> None:
        self.ledger.observation = "with_resources" if observations else "empty"
        self.ledger.observations = [dict(item) for item in observations]

    def record_schedule_failure(self) -> None:
        if self.ledger.schedule_check != "checked":
            self.ledger.schedule_check = "unavailable"

    def record_schedule(self, facts: dict[str, object]) -> None:
        classifications = facts.get("classifications")
        appointments = facts.get("appointments")
        if not isinstance(classifications, list) or not isinstance(appointments, list):
            self.record_schedule_failure()
            return
        self.ledger.schedule_check = "checked"
        self.ledger.classifications = tuple(str(item) for item in classifications)
        if classifications == [NONE]:
            self.ledger.appointments = ()
            return
        rows: list[tuple[str, str]] = []
        for item in appointments:
            if not isinstance(item, dict):
                continue
            appointment_id = item.get("id")
            classification = item.get("classification")
            if isinstance(appointment_id, str) and appointment_id and isinstance(classification, str):
                rows.append((f"Appointment/{appointment_id}", classification))
        self.ledger.appointments = tuple(rows)

    def preserved_reads(self) -> dict[str, object]:
        """Resources already read. A later failure does not erase them or invent the rest."""
        patient = None
        observations: list[dict] = []
        evidence: list[dict[str, object]] = []
        tools: list[str] = []
        if self.ledger.patient == "resolved" and isinstance(self.ledger.patient_resource, dict):
            patient = dict(self.ledger.patient_resource)
            if self.ledger.observation in {"with_resources", "empty"} and self.ledger.observations is not None:
                observations = [dict(item) for item in self.ledger.observations]
            evidence.append({"tool": FOLLOWUP_TOOL, "resources": _resource_refs(patient, observations)})
            tools.append(FOLLOWUP_TOOL)
        if self.ledger.schedule_check == "checked":
            refs = [appointment_id for appointment_id, _classification in self.ledger.appointments]
            if refs:
                evidence.append({"tool": APPOINTMENTS_TOOL, "resources": refs})
            tools.append(APPOINTMENTS_TOOL)
        return {
            "patient": patient,
            "observations": observations,
            "evidence": evidence,
            "tools_used": tools,
        }

    def patient_id_for_case(self, case_id: str) -> str:
        """Resolve the authorized case. A different case id does not build a query."""
        scope = _READ_SCOPE.get()
        if scope is None or not isinstance(case_id, str) or case_id != scope.case_id:
            raise ReadClientError("case id is not authorized for this run")
        authorized = scope.case_id
        _mark("adapter:patient_for_case")
        self.calls.append(("patient_for_case", authorized))
        payload = self.transport.get(case_search_path(authorized))
        return _patient_id_from_case_search(payload, authorized)

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

    def get_patient_appointments(self, patient_id: str, now: datetime | None = None) -> dict[str, object]:
        """Read this patient's appointments and label each operational fact. An empty search is NONE."""
        _mark("adapter:get_patient_appointments")
        self.calls.append(("get_patient_appointments", patient_id))
        payload = self.transport.get(appointment_search_path(patient_id))
        return appointment_facts(payload, patient_id, now or self._now())


def appointment_search_path(patient_id: str) -> str:
    """Search Appointment by patient. The patient id is resolved by the application, not by the model."""
    if not isinstance(patient_id, str) or _PATIENT_ID_TOKEN.fullmatch(patient_id) is None:
        raise ReadClientError("patient id is not usable")
    return f"Appointment?patient=Patient/{patient_id}"


def _actor_is_patient(reference: object, patient_id: str) -> bool:
    if not isinstance(reference, str) or not reference:
        return False
    expected = f"Patient/{patient_id}"
    return reference == expected or reference.endswith(f"/{expected}")


def _parsed_start(raw: object) -> datetime | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        start = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    return start


def appointment_classification(status: object, start: object, now: datetime) -> str:
    """Label one Appointment as an operational fact. This does not decide follow-up."""
    if status == "cancelled":
        return CANCELLED
    parsed = _parsed_start(start)
    future = parsed is not None and parsed >= now
    past = parsed is not None and parsed < now
    if status == "booked" and future:
        return UPCOMING_CONFIRMED
    if status in _UNCONFIRMED_STATUS and future:
        return UPCOMING_UNCONFIRMED
    if status in _PAST_STATUS and past:
        return PAST
    return OTHER


def schedule_classifications(appointments: list[dict]) -> list[str]:
    """Summarize labels that were actually read. An empty list is NONE, not an invented id."""
    if not appointments:
        return [NONE]
    found = {item.get("classification") for item in appointments}
    return [name for name in _CLASS_ORDER if name in found]


def _appointment_view(resource: dict, patient_id: str, now: datetime) -> dict | None:
    """Keep a visit that belongs to this patient. Other patients are omitted."""
    participants = resource.get("participant")
    if not isinstance(participants, list):
        return None
    matched = False
    for item in participants:
        actor = item.get("actor") if isinstance(item, dict) else None
        reference = actor.get("reference") if isinstance(actor, dict) else None
        if _actor_is_patient(reference, patient_id):
            matched = True
            break
    if not matched:
        return None
    appointment_id = resource.get("id")
    if not isinstance(appointment_id, str) or not appointment_id:
        raise ReadClientError("appointment has no id")
    view = {
        "resourceType": "Appointment",
        "id": appointment_id,
        "status": resource.get("status"),
        "patient": f"Patient/{patient_id}",
        "classification": appointment_classification(resource.get("status"), resource.get("start"), now),
    }
    start = resource.get("start")
    if isinstance(start, str) and start.strip() and _parsed_start(start) is not None:
        view["start"] = start.strip()
    return view


def appointment_facts(payload: dict, patient_id: str, now: datetime) -> dict[str, object]:
    """Classify appointments returned for one patient. The query is chosen by the caller."""
    if payload.get("resourceType") != "Bundle":
        raise ReadClientError("appointment response must be a bundle")
    entries = payload.get("entry") or []
    if not isinstance(entries, list):
        raise ReadClientError("appointment bundle entries must be a list")
    appointments: list[dict] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ReadClientError("bundle entry must be an object")
        resource = entry.get("resource")
        if not isinstance(resource, dict) or resource.get("resourceType") != "Appointment":
            raise ReadClientError("bundle entry must contain an appointment")
        view = _appointment_view(resource, patient_id, now)
        if view is not None:
            appointments.append(view)
    return {
        "patientId": patient_id,
        "classifications": schedule_classifications(appointments),
        "appointments": appointments,
    }


def make_followup_tool(adapter: FollowUpFHIRAdapter):
    """Build the follow-up read. The tool sees the adapter and the case id."""

    @tool
    def get_patient_followup_context(case_id: str) -> dict[str, object]:
        """Read one case through the adapter."""
        _mark(f"execute:{FOLLOWUP_TOOL}")
        try:
            patient_id = adapter.patient_id_for_case(case_id)
        except ReadClientError as exc:
            adapter.record_patient_search_failure(exc)
            raise
        try:
            patient = adapter.get_patient(patient_id)
        except ReadClientError:
            adapter.record_patient_read_failure()
            raise
        adapter.record_patient_resolved(patient)
        try:
            observations = adapter.get_observations(patient_id)
        except ReadClientError:
            adapter.record_observation_failure()
            raise
        adapter.record_observations(observations)
        return {"patient": patient, "observations": observations}

    return get_patient_followup_context


def make_appointments_tool(adapter: FollowUpFHIRAdapter):
    """Build the appointment read. The model supplies a case id. The adapter resolves the patient."""

    @tool
    def get_patient_appointments(case_id: str) -> dict[str, object]:
        """Read appointment facts for the patient linked to one follow-up case."""
        _mark(f"execute:{APPOINTMENTS_TOOL}")
        try:
            patient_id = adapter.patient_id_for_case(case_id)
            facts = adapter.get_patient_appointments(patient_id)
        except ReadClientError:
            adapter.record_schedule_failure()
            raise
        adapter.record_schedule(facts)
        return facts

    return get_patient_appointments


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


def _appointment_refs(appointments: list[dict]) -> list[str]:
    refs: list[str] = []
    for resource in appointments:
        appointment_id = resource.get("id")
        if not isinstance(appointment_id, str) or not appointment_id:
            raise ReadClientError("appointment has no id")
        refs.append(f"Appointment/{appointment_id}")
    return refs
