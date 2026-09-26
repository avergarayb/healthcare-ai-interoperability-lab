"""Read boundary for the follow-up workflow. This module is not a graph.

Policy and audit are application functions. The transport forwards one path
to a FHIRReadClient. The prepared client is an in-memory stand-in for tests.
HTTP lives in HapiReadClient.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
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
ALLOWED_READ_TOOLS = frozenset({FOLLOWUP_TOOL})
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


def clear_boundary_events() -> None:
    BOUNDARY_EVENTS.clear()


def default_clock() -> str:
    return DEFAULT_TIMESTAMP


class ReadClientError(Exception):
    """A read client could not return a response."""


class FHIRReadClient(Protocol):
    def get(self, path: str) -> dict: ...


class FHIRTransport(Protocol):
    def get(self, path: str) -> dict: ...


class FHIRAdapter(Protocol):
    def get_patient(self, patient_id: str) -> dict: ...

    def get_observations(self, patient_id: str) -> list[dict]: ...


def _patient_resource(patient_id: str) -> dict[str, str]:
    return {"resourceType": "Patient", "id": patient_id}


def _prepared_case_match(path: str) -> tuple[str, str] | None:
    """The one prepared record is addressed by its case identifier, not by Patient.id."""
    prefix = "Patient?identifier="
    if not path.startswith(prefix):
        return None
    system, separator, value = unquote(path[len(prefix) :]).partition("|")
    if separator and system and value == PATIENT_CASE:
        return system, value
    return None


def _observation_resource(observation_id: str, patient_id: str, value: str) -> dict[str, object]:
    return {
        "resourceType": "Observation",
        "id": observation_id,
        "status": "final",
        "subject": {"reference": f"Patient/{patient_id}"},
        "valueString": value,
    }


def _bundle(observation: dict[str, object]) -> dict[str, object]:
    return {"resourceType": "Bundle", "type": "searchset", "entry": [{"resource": observation}]}


class PreparedReadClient:
    """In-memory responses for one patient and one observation. No network."""

    def __init__(
        self,
        *,
        observation_id: str = "obs-synthetic-001",
        observation_value: str = "Synthetic observation result",
    ) -> None:
        self.observation_id = observation_id
        self.observation_value = observation_value
        self.calls: list[str] = []

    def get(self, path: str) -> dict:
        BOUNDARY_EVENTS.append(f"client:{path}")
        self.calls.append(path)
        matched = _prepared_case_match(path)
        if matched is not None:
            patient = _patient_resource(PATIENT_ID)
            patient["identifier"] = [{"system": matched[0], "value": matched[1]}]
            return {"resourceType": "Bundle", "type": "searchset", "entry": [{"resource": patient}]}
        if path.startswith("Patient?identifier="):
            return {"resourceType": "Bundle", "type": "searchset", "entry": []}
        if path == f"Patient/{PATIENT_ID}":
            return _patient_resource(PATIENT_ID)
        if path == f"Observation?subject=Patient/{PATIENT_ID}":
            return _bundle(_observation_resource(self.observation_id, PATIENT_ID, self.observation_value))
        raise ReadClientError("unknown prepared path")


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

    def record(self, event: PolicyAuditEvent) -> None:
        """Append one audit event."""


class InMemoryAuditSink:
    """Laboratory sink. It keeps events in a list and does not leave the process."""

    def __init__(self) -> None:
        self.events: list[PolicyAuditEvent] = []

    def record(self, event: PolicyAuditEvent) -> None:
        expected = len(self.events) + 1
        if event.sequence != expected:
            raise ValueError("audit sequence must be contiguous")
        if self.events and event.run_id != self.events[0].run_id:
            raise ValueError("audit run_id must stay constant")
        self.events.append(event)


def evaluate_tool_policy(tool_name: str) -> PolicyDecision:
    """Decide whether a proposed tool may run. This function has no graph types."""
    if tool_name in ALLOWED_READ_TOOLS:
        decision = PolicyDecision("allowed", "read tool is allowed")
    elif tool_name == "send_message":
        decision = PolicyDecision("denied", "external effect is not allowed")
    else:
        decision = PolicyDecision("denied", "unknown tool is not allowed")
    BOUNDARY_EVENTS.append(f"policy:{tool_name}:{decision.status}")
    return decision


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
    event = PolicyAuditEvent(
        sequence=len(sink.events) + 1,
        timestamp=timestamp,
        run_id=run_id,
        case_id=case_id,
        tool_name=tool_name,
        decision=decision,
        reason=reason,
        policy_version=POLICY_VERSION,
    )
    BOUNDARY_EVENTS.append(f"audit:{tool_name}:{decision}")
    sink.record(event)
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
