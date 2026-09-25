"""Read-only synthetic Follow-up Agent tools. Local registry only; no HTTP or policy."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Callable

from app.followup_fixtures import get_followup_fixture


class ToolError(Exception):
    """Base error for local tool lookup and execution."""


class UnknownToolError(ToolError):
    def __init__(self, name: str) -> None:
        super().__init__(f"unknown tool: {name}")
        self.name = name


class DuplicateToolError(ToolError):
    def __init__(self, name: str) -> None:
        super().__init__(f"duplicate tool: {name}")
        self.name = name


class ToolInputError(ToolError):
    def __init__(self, message: str) -> None:
        super().__init__(message)


class ToolFixtureNotFound(ToolError):
    def __init__(self, case_id: str) -> None:
        super().__init__(f"unknown caseId: {case_id}")
        self.case_id = case_id


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    resources: tuple[str, ...]
    fn: Callable[[Any], dict[str, Any]]


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, tool: ToolSpec) -> None:
        if tool.name in self._tools:
            raise DuplicateToolError(tool.name)
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolSpec:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise UnknownToolError(name) from exc

    def names(self) -> tuple[str, ...]:
        return tuple(self._tools)


def parse_tool_case_id(payload: Any) -> str:
    if not isinstance(payload, dict):
        raise ToolInputError("tool input must be an object")
    extra = set(payload) - {"caseId"}
    if extra:
        raise ToolInputError("tool input contains unsupported fields")
    if "caseId" not in payload:
        raise ToolInputError("caseId is required")
    case_id = payload["caseId"]
    if not isinstance(case_id, str) or case_id.strip() == "" or case_id != case_id.strip():
        raise ToolInputError("caseId must be a non-empty string")
    return case_id


def _read(tool_name: str, resource: str, payload: Any) -> dict[str, Any]:
    case_id = parse_tool_case_id(payload)
    try:
        fixture = get_followup_fixture(case_id)
    except KeyError as exc:
        raise ToolFixtureNotFound(case_id) from exc
    return {
        "tool": tool_name,
        "caseId": case_id,
        "data": deepcopy(fixture[resource]),
    }


def get_patient(payload: Any) -> dict[str, Any]:
    return _read("get_patient", "patient", payload)


def get_recent_encounters(payload: Any) -> dict[str, Any]:
    return _read("get_recent_encounters", "encounters", payload)


def get_conditions(payload: Any) -> dict[str, Any]:
    return _read("get_conditions", "conditions", payload)


def get_recent_observations(payload: Any) -> dict[str, Any]:
    return _read("get_recent_observations", "observations", payload)


def get_medications(payload: Any) -> dict[str, Any]:
    return _read("get_medications", "medications", payload)


def get_upcoming_appointments(payload: Any) -> dict[str, Any]:
    return _read("get_upcoming_appointments", "appointments", payload)


FOLLOWUP_TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec(
        name="get_patient",
        description="Retrieve the synthetic patient context for a follow-up case.",
        resources=("patient",),
        fn=get_patient,
    ),
    ToolSpec(
        name="get_recent_encounters",
        description="Retrieve synthetic encounters recorded for a follow-up case.",
        resources=("encounters",),
        fn=get_recent_encounters,
    ),
    ToolSpec(
        name="get_conditions",
        description="Retrieve synthetic conditions recorded for a follow-up case.",
        resources=("conditions",),
        fn=get_conditions,
    ),
    ToolSpec(
        name="get_recent_observations",
        description="Retrieve synthetic observations recorded for a follow-up case.",
        resources=("observations",),
        fn=get_recent_observations,
    ),
    ToolSpec(
        name="get_medications",
        description="Retrieve synthetic medications recorded for a follow-up case.",
        resources=("medications",),
        fn=get_medications,
    ),
    ToolSpec(
        name="get_upcoming_appointments",
        description="Retrieve synthetic appointments recorded for a follow-up case.",
        resources=("appointments",),
        fn=get_upcoming_appointments,
    ),
)


def build_followup_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    for tool in FOLLOWUP_TOOLS:
        registry.register(tool)
    return registry
