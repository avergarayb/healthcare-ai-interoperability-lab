from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest

from app.followup_fixtures import CONTEXT_KEYS, FOLLOWUP_FIXTURES
from app.followup_models import CASE_IDS
from app.followup_tools import (
    DuplicateToolError,
    FOLLOWUP_TOOLS,
    ToolFixtureNotFound,
    ToolInputError,
    ToolSpec,
    UnknownToolError,
    build_followup_tool_registry,
    get_conditions,
    get_medications,
    get_patient,
    get_recent_encounters,
    get_recent_observations,
    get_upcoming_appointments,
)

EXPECTED_TOOLS = {
    "get_patient": ("patient", get_patient),
    "get_recent_encounters": ("encounters", get_recent_encounters),
    "get_conditions": ("conditions", get_conditions),
    "get_recent_observations": ("observations", get_recent_observations),
    "get_medications": ("medications", get_medications),
    "get_upcoming_appointments": ("appointments", get_upcoming_appointments),
}


def _payload(case_id: str = "SYN-FOLLOWUP-001") -> dict[str, str]:
    return {"caseId": case_id}


def _walk(value: Any):
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from _walk(nested)
    elif isinstance(value, list):
        for item in value:
            yield from _walk(item)


def test_registry_contains_exactly_the_six_tools():
    registry = build_followup_tool_registry()
    assert registry.names() == tuple(EXPECTED_TOOLS)
    assert len(FOLLOWUP_TOOLS) == 6
    assert {tool.name for tool in FOLLOWUP_TOOLS} == set(EXPECTED_TOOLS)


def test_registry_names_match_expected_order():
    assert build_followup_tool_registry().names() == (
        "get_patient",
        "get_recent_encounters",
        "get_conditions",
        "get_recent_observations",
        "get_medications",
        "get_upcoming_appointments",
    )


def test_registry_get_returns_registered_tool():
    registry = build_followup_tool_registry()
    tool = registry.get("get_conditions")
    assert isinstance(tool, ToolSpec)
    assert tool.name == "get_conditions"
    assert tool.resources == ("conditions",)
    assert tool.fn is get_conditions
    assert "synthetic conditions" in tool.description.lower()


def test_registry_get_unknown_tool_fails_deterministically():
    registry = build_followup_tool_registry()
    with pytest.raises(UnknownToolError, match="unknown tool: create_appointment"):
        registry.get("create_appointment")


def test_duplicate_registration_fails():
    registry = build_followup_tool_registry()
    with pytest.raises(DuplicateToolError, match="duplicate tool: get_patient"):
        registry.register(FOLLOWUP_TOOLS[0])


@pytest.mark.parametrize("case_id", CASE_IDS)
@pytest.mark.parametrize(
    "tool_name, resource, fn",
    [(name, spec[0], spec[1]) for name, spec in EXPECTED_TOOLS.items()],
)
def test_each_tool_reads_its_domain_from_every_fixture(case_id, tool_name, resource, fn):
    result = fn(_payload(case_id))
    assert result["tool"] == tool_name
    assert result["caseId"] == case_id
    assert result["data"] == FOLLOWUP_FIXTURES[case_id][resource]
    assert result["data"] is not FOLLOWUP_FIXTURES[case_id][resource]


def test_get_patient_returns_patient():
    result = get_patient(_payload())
    assert result["data"] == FOLLOWUP_FIXTURES["SYN-FOLLOWUP-001"]["patient"]
    assert result["data"]["id"] == "SYN-PAT-001"


def test_get_recent_encounters_returns_encounters():
    result = get_recent_encounters(_payload())
    assert result["data"] == FOLLOWUP_FIXTURES["SYN-FOLLOWUP-001"]["encounters"]


def test_get_conditions_returns_conditions():
    result = get_conditions(_payload())
    assert result["data"] == FOLLOWUP_FIXTURES["SYN-FOLLOWUP-001"]["conditions"]


def test_get_recent_observations_returns_observations():
    result = get_recent_observations(_payload())
    assert result["data"] == FOLLOWUP_FIXTURES["SYN-FOLLOWUP-001"]["observations"]


def test_get_medications_returns_medications():
    result = get_medications(_payload())
    assert result["data"] == FOLLOWUP_FIXTURES["SYN-FOLLOWUP-001"]["medications"]


def test_get_upcoming_appointments_returns_appointments():
    result = get_upcoming_appointments(_payload())
    assert result["data"] == FOLLOWUP_FIXTURES["SYN-FOLLOWUP-001"]["appointments"]
    assert result["data"][0]["id"] == "SYN-APT-001"


def test_unknown_case_id_is_a_controlled_error():
    with pytest.raises(ToolFixtureNotFound, match="unknown caseId: SYN-FOLLOWUP-999"):
        get_patient({"caseId": "SYN-FOLLOWUP-999"})


def test_invalid_input_is_a_controlled_error():
    with pytest.raises(ToolInputError):
        get_patient({"resourceType": "Bundle", "type": "collection", "entry": []})
    with pytest.raises(ToolInputError):
        get_patient({"caseId": "SYN-FOLLOWUP-001", "patientId": "external-id"})
    with pytest.raises(ToolInputError):
        get_patient("SYN-FOLLOWUP-001")
    with pytest.raises(ToolInputError):
        get_conditions({})


def test_tool_results_do_not_include_resource_type():
    for fn in (item[1] for item in EXPECTED_TOOLS.values()):
        result = fn(_payload("SYN-FOLLOWUP-005"))
        for node in _walk(result):
            assert "resourceType" not in node
            assert "resource_type" not in node


def test_tools_do_not_mutate_fixtures():
    snapshot = deepcopy(FOLLOWUP_FIXTURES["SYN-FOLLOWUP-001"])
    result = get_patient(_payload())
    result["data"]["display"] = "mutated"
    result["data"]["id"] = "SYN-PAT-MUTATED"
    appointments = get_upcoming_appointments(_payload())
    appointments["data"][0]["status"] = "cancelled"
    assert FOLLOWUP_FIXTURES["SYN-FOLLOWUP-001"] == snapshot


def test_tools_are_read_only_getters():
    assert all(name.startswith("get_") for name in EXPECTED_TOOLS)
    assert CONTEXT_KEYS == (
        "patient",
        "encounters",
        "conditions",
        "observations",
        "medications",
        "appointments",
    )
    for tool in FOLLOWUP_TOOLS:
        assert len(tool.resources) == 1
        assert tool.resources[0] in CONTEXT_KEYS


def test_registry_does_not_execute_tools():
    registry = build_followup_tool_registry()
    spec = registry.get("get_patient")
    assert spec.fn is get_patient
    assert registry.get("get_patient") is spec
