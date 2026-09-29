"""Read boundary for the follow-up workflow. This module is not a graph.

Policy and audit are application functions. The transport forwards one path
to a FHIRReadClient. The prepared client is an in-memory stand-in for tests.
HTTP lives in HapiReadClient.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from enum import Enum
from typing import Protocol
from urllib.parse import unquote

from langchain_core.tools import tool


log = logging.getLogger("ai-service")


PATIENT_CASE = "SYN-FOLLOWUP-001"
PATIENT_ID = "SYN-PATIENT-001"
CASE_IDENTIFIER_SYSTEM = "https://lab.local/followup-case"
DENIAL_ANSWER = "Tool denied by policy"
POLICY_VERSION = "policy-v1"
DEFAULT_TIMESTAMP = "1970-01-01T00:00:00Z"
FOLLOWUP_TOOL = "get_patient_followup_context"
APPOINTMENTS_TOOL = "get_patient_appointments"
APPOINTMENT_ID = "appointment-synthetic-001"
ALLOWED_READ_TOOLS = frozenset({FOLLOWUP_TOOL, APPOINTMENTS_TOOL})
SAFE_AUDIT_FIELDS = (
    "sequence",
    "timestamp",
    "run_id",
    "case_id",
    "tool_name",
    "decision",
    "reason",
    "policy_version",
)

BOUNDARY_EVENTS: list[str] = []
FHIR_SEARCH_PAGE_SIZE = 25
FHIR_SEARCH_MAX_PAGES = 4
FHIR_SEARCH_MAX_UNIQUE_RESOURCES_PER_TYPE = 100
FHIR_NEXT_URL_MAX_LENGTH = 4096


def clear_boundary_events() -> None:
    BOUNDARY_EVENTS.clear()


def default_clock() -> str:
    return DEFAULT_TIMESTAMP


class ReadClientError(Exception):
    """A read client could not return a response."""


class BoundedSearchStatus(str, Enum):
    COMPLETE = "complete"
    INCOMPLETE_LIMIT = "incomplete_limit"
    FAILED = "failed"


@dataclass(frozen=True)
class BoundedSearchResult:
    status: BoundedSearchStatus
    resources: tuple[dict, ...]
    reason: str | None = None


class FHIRReadClient(Protocol):
    def get(self, path: str) -> dict: ...

    def search(self, path: str, expected_resource_type: str) -> BoundedSearchResult: ...


class FHIRTransport(Protocol):
    def get(self, path: str) -> dict: ...

    def search(self, path: str, expected_resource_type: str) -> BoundedSearchResult: ...


class FHIRAdapter(Protocol):
    def get_patient(self, patient_id: str) -> dict: ...

    def get_observations(self, patient_id: str) -> list[dict]: ...


def bundle_list_field(payload: dict, field: str, error: str) -> list:
    """Return an optional Bundle array without treating invalid falsy values as absent."""
    if field not in payload:
        return []
    value = payload[field]
    if not isinstance(value, list):
        raise ReadClientError(error)
    return value


def _patient_resource(patient_id: str) -> dict[str, str]:
    return {"resourceType": "Patient", "id": patient_id}


def _prepared_case_match(path: str, case_id: str = PATIENT_CASE) -> tuple[str, str] | None:
    """A prepared record is addressed by its case identifier, not by Patient.id."""
    prefix = "Patient?identifier="
    if not path.startswith(prefix):
        return None
    identifier = path[len(prefix) :].split("&", 1)[0]
    system, separator, value = unquote(identifier).partition("|")
    if separator and system and value == case_id:
        return system, value
    return None


def _observation_resource(observation_id: str, patient_id: str, value: str) -> dict[str, object]:
    return {
        "resourceType": "Observation",
        "id": observation_id,
        "status": "final",
        "subject": {"reference": f"Patient/{patient_id}"},
        "encounter": {"reference": "Encounter/encounter-synthetic-001"},
        "issued": "2026-09-25T12:30:00Z",
        "valueString": value,
    }


def _bundle(observation: dict[str, object]) -> dict[str, object]:
    return {"resourceType": "Bundle", "type": "searchset", "entry": [{"resource": observation}]}


def synthetic_followup_appointment() -> dict[str, object]:
    """One future booked visit for the follow-up patient. Not a record of another patient."""
    return {
        "resourceType": "Appointment",
        "id": APPOINTMENT_ID,
        "status": "booked",
        "description": "Synthetic follow-up visit",
        "start": "2027-03-15T15:00:00Z",
        "end": "2027-03-15T15:30:00Z",
        "participant": [
            {
                "actor": {"reference": f"Patient/{PATIENT_ID}"},
                "status": "accepted",
            }
        ],
    }


def synthetic_appointment(
    *,
    appointment_id: str,
    status: str,
    start: str | None,
    patient_id: str,
) -> dict[str, object]:
    """One synthetic Appointment. Status and start stay on the resource; they are not a clinical rule."""
    resource: dict[str, object] = {
        "resourceType": "Appointment",
        "id": appointment_id,
        "status": status,
        "participant": [
            {
                "actor": {"reference": f"Patient/{patient_id}"},
                "status": "accepted",
            }
        ],
    }
    if start is not None:
        resource["start"] = start
    return resource


class PreparedReadClient:
    """In-memory FHIR reads for one prepared case. No network."""

    def __init__(
        self,
        *,
        case_id: str = PATIENT_CASE,
        patient_id: str = PATIENT_ID,
        observation_id: str = "obs-synthetic-001",
        observation_value: str = "Synthetic observation result",
        observations: list[dict[str, object]] | None = None,
        encounters: list[dict[str, object]] | None = None,
        appointments: list[dict[str, object]] | None = None,
        fail_observation_read: bool = False,
        fail_encounter_read: bool = False,
        fail_appointment_read: bool = False,
    ) -> None:
        self.case_id = case_id
        self.patient_id = patient_id
        self.fail_observation_read = fail_observation_read
        self.fail_encounter_read = fail_encounter_read
        self.fail_appointment_read = fail_appointment_read
        if observations is None:
            self.observations = [_observation_resource(observation_id, patient_id, observation_value)]
        else:
            self.observations = [dict(item) for item in observations]
        self.encounters = (
            [
                {
                    "resourceType": "Encounter",
                    "id": "encounter-synthetic-001",
                    "status": "finished",
                    "subject": {"reference": f"Patient/{patient_id}"},
                    "period": {
                        "start": "2026-09-25T11:00:00Z",
                        "end": "2026-09-25T12:00:00Z",
                    },
                }
            ]
            if encounters is None
            else [dict(item) for item in encounters]
        )
        self.appointments = (
            [
                synthetic_appointment(
                    appointment_id=APPOINTMENT_ID,
                    status="booked",
                    start="2027-03-15T15:00:00Z",
                    patient_id=patient_id,
                )
            ]
            if appointments is None
            else [dict(item) for item in appointments]
        )
        self.calls: list[str] = []

    def get(self, path: str) -> dict:
        BOUNDARY_EVENTS.append(f"client:{path}")
        self.calls.append(path)
        matched = _prepared_case_match(path, self.case_id)
        if matched is not None:
            patient = _patient_resource(self.patient_id)
            patient["identifier"] = [{"system": matched[0], "value": matched[1]}]
            return {"resourceType": "Bundle", "type": "searchset", "entry": [{"resource": patient}]}
        if path.startswith("Patient?identifier="):
            return {"resourceType": "Bundle", "type": "searchset", "entry": []}
        if path == f"Patient/{self.patient_id}":
            return _patient_resource(self.patient_id)
        if path in {
            f"Observation?subject=Patient/{self.patient_id}",
            f"Observation?subject=Patient/{self.patient_id}&status=final&_count=25",
        }:
            if self.fail_observation_read:
                raise ReadClientError("HTTP 503")
            return {
                "resourceType": "Bundle",
                "type": "searchset",
                "entry": [{"resource": dict(item)} for item in self.observations],
            }
        if path == f"Encounter?patient=Patient/{self.patient_id}&status=finished&_count=25":
            if self.fail_encounter_read:
                raise ReadClientError("HTTP 503")
            return {
                "resourceType": "Bundle",
                "type": "searchset",
                "entry": [{"resource": dict(item)} for item in self.encounters],
            }
        if path in {
            f"Appointment?patient=Patient/{self.patient_id}",
            f"Appointment?patient=Patient/{self.patient_id}&_count=25",
        }:
            if self.fail_appointment_read:
                raise ReadClientError("HTTP 503")
            return {
                "resourceType": "Bundle",
                "type": "searchset",
                "entry": [{"resource": dict(item)} for item in self.appointments],
            }
        raise ReadClientError("unknown prepared path")

    def search(self, path: str, expected_resource_type: str) -> BoundedSearchResult:
        try:
            payload = self.get(path)
            resources = _single_page_resources(payload, expected_resource_type)
        except ReadClientError as exc:
            return BoundedSearchResult(BoundedSearchStatus.FAILED, (), str(exc))
        return BoundedSearchResult(BoundedSearchStatus.COMPLETE, tuple(resources))


class FailingPreparedReadClient:
    """A client that fails on every read."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def get(self, path: str) -> dict:
        BOUNDARY_EVENTS.append(f"client:{path}")
        self.calls.append(path)
        raise ReadClientError("prepared client failed")


class ClientFHIRTransport:
    """Forward one path to the injected client. This class stores no records."""

    def __init__(self, client: FHIRReadClient) -> None:
        self.client = client
        self.calls: list[str] = []

    def get(self, path: str) -> dict:
        BOUNDARY_EVENTS.append(f"transport:{path}")
        self.calls.append(path)
        return self.client.get(path)

    def search(self, path: str, expected_resource_type: str) -> BoundedSearchResult:
        BOUNDARY_EVENTS.append(f"transport:{path}")
        self.calls.append(path)
        search = getattr(self.client, "search", None)
        if callable(search):
            return search(path, expected_resource_type)
        try:
            payload = self.client.get(path)
            resources = _single_page_resources(payload, expected_resource_type)
        except ReadClientError as exc:
            return BoundedSearchResult(BoundedSearchStatus.FAILED, (), str(exc))
        try:
            links = bundle_list_field(payload, "link", "search bundle links are malformed")
        except ReadClientError as exc:
            return BoundedSearchResult(BoundedSearchStatus.FAILED, tuple(resources), str(exc))
        if any(not isinstance(item, dict) for item in links):
            return BoundedSearchResult(
                BoundedSearchStatus.FAILED,
                tuple(resources),
                "search bundle links are malformed",
            )
        if any(item.get("relation") == "next" for item in links):
            return BoundedSearchResult(
                BoundedSearchStatus.FAILED,
                tuple(resources),
                "read client does not support bounded pagination",
            )
        return BoundedSearchResult(BoundedSearchStatus.COMPLETE, tuple(resources))


def _single_page_resources(payload: dict, expected_resource_type: str) -> list[dict]:
    if payload.get("resourceType") != "Bundle" or payload.get("type") != "searchset":
        raise ReadClientError("search response must be a searchset bundle")
    entries = bundle_list_field(payload, "entry", "search bundle entries must be a list")
    resources: list[dict] = []
    by_identity: dict[tuple[str, str], dict] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ReadClientError("bundle entry must be an object")
        resource = entry.get("resource")
        if not isinstance(resource, dict) or resource.get("resourceType") != expected_resource_type:
            raise ReadClientError(f"bundle entry must contain {expected_resource_type}")
        resource_id = resource.get("id")
        if not isinstance(resource_id, str) or not resource_id:
            raise ReadClientError("search resource has no id")
        identity = (expected_resource_type, resource_id)
        prior = by_identity.get(identity)
        if prior is not None:
            if prior != resource:
                raise ReadClientError("conflicting duplicate search resource")
            continue
        copied = dict(resource)
        by_identity[identity] = copied
        resources.append(copied)
    return resources


@dataclass(frozen=True)
class PolicyDecision:
    status: str
    reason: str


@dataclass(frozen=True)
class PolicyAuditEvent:
    sequence: int
    timestamp: str
    run_id: str
    case_id: str
    tool_name: str
    decision: str
    reason: str
    policy_version: str


class AuditRecorder(Protocol):
    events: list[PolicyAuditEvent]

    def record(
        self,
        *,
        timestamp: str,
        run_id: str,
        case_id: str,
        tool_name: str,
        decision: str,
        reason: str,
        policy_version: str,
    ) -> PolicyAuditEvent:
        """Allocate and append one audit event atomically."""


class InMemoryAuditSink:
    """Laboratory sink. It keeps events in a list and does not leave the process."""

    def __init__(self) -> None:
        self.events: list[PolicyAuditEvent] = []
        self._lock = threading.Lock()

    def record(
        self,
        *,
        timestamp: str,
        run_id: str,
        case_id: str,
        tool_name: str,
        decision: str,
        reason: str,
        policy_version: str,
    ) -> PolicyAuditEvent:
        with self._lock:
            if self.events and run_id != self.events[0].run_id:
                raise ValueError("audit run_id must stay constant")
            event = PolicyAuditEvent(
                sequence=len(self.events) + 1,
                timestamp=timestamp,
                run_id=run_id,
                case_id=case_id,
                tool_name=tool_name,
                decision=decision,
                reason=reason,
                policy_version=policy_version,
            )
            self.events.append(event)
            return event


CASE_ID_MISMATCH_REASON = "case_id_mismatch"


def evaluate_tool_policy(
    tool_name: str,
    *,
    authorized_case_id: str | None = None,
    proposed_case_id: object | None = None,
) -> PolicyDecision:
    """Decide whether a proposed tool may run. This function has no graph types.

    A name-only call keeps the previous name check. When the caller supplies the
    authorized case, a clinical read must propose that same case id.
    """
    if tool_name in ALLOWED_READ_TOOLS:
        if authorized_case_id is not None and not _same_authorized_case(authorized_case_id, proposed_case_id):
            decision = PolicyDecision("denied", CASE_ID_MISMATCH_REASON)
        else:
            decision = PolicyDecision("allowed", "read tool is allowed")
    elif tool_name == "send_message":
        decision = PolicyDecision("denied", "external effect is not allowed")
    else:
        decision = PolicyDecision("denied", "unknown tool is not allowed")
    BOUNDARY_EVENTS.append(f"policy:{tool_name}:{decision.status}")
    return decision


def _same_authorized_case(authorized_case_id: str, proposed_case_id: object | None) -> bool:
    return isinstance(proposed_case_id, str) and proposed_case_id == authorized_case_id


def record_policy_audit(
    sink: AuditRecorder,
    *,
    run_id: str,
    case_id: str,
    tool_name: str,
    decision: str,
    reason: str,
    timestamp: str,
) -> PolicyAuditEvent:
    """Record one policy verdict. The event stores the operational fields only."""
    if decision not in {"allowed", "denied"}:
        raise ValueError("unknown policy decision")
    BOUNDARY_EVENTS.append(f"audit:{tool_name}:{decision}")
    event = sink.record(
        timestamp=timestamp,
        run_id=run_id,
        case_id=case_id,
        tool_name=tool_name,
        decision=decision,
        reason=reason,
        policy_version=POLICY_VERSION,
    )
    _log_policy_audit(event)
    return event


def _log_policy_audit(event: PolicyAuditEvent) -> None:
    """Emit the existing audit event. The line carries only the operational fields."""
    line = (
        "followup_tool_policy_audit "
        f"run_id={event.run_id} "
        f"case_id={event.case_id} "
        f"tool_name={event.tool_name} "
        f"decision={event.decision} "
        f"policy_version={event.policy_version} "
        f"reason={event.reason}"
    )
    lowered = line.lower()
    if "x-service-token=" in lowered or "gemini_api_key=" in lowered:
        raise RuntimeError("policy audit log line must not contain secrets")
    log.info(line)


@tool
def send_message(patient_id: str, body: str) -> dict[str, str]:
    """Synthetic external effect. The policy boundary must stop this tool."""
    BOUNDARY_EVENTS.append(f"execute:{send_message.name}")
    return {"patientId": patient_id, "body": body, "delivered": "yes"}
