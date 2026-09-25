from __future__ import annotations

from typing import Any

import pytest

from app.followup_fixtures import (
    CONTEXT_KEYS,
    FIXTURE_INTENTS,
    FOLLOWUP_FIXTURES,
    get_followup_fixture,
)
from app.followup_models import CASE_IDS


def _walk(value: Any):
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from _walk(nested)
    elif isinstance(value, list):
        for item in value:
            yield from _walk(item)


def test_all_six_fixtures_exist():
    assert tuple(FOLLOWUP_FIXTURES) == CASE_IDS
    assert set(FIXTURE_INTENTS) == set(CASE_IDS)
    for case_id in CASE_IDS:
        assert get_followup_fixture(case_id) is FOLLOWUP_FIXTURES[case_id]


def test_each_fixture_has_synthetic_clinical_context_keys():
    for case_id, fixture in FOLLOWUP_FIXTURES.items():
        assert tuple(key for key in CONTEXT_KEYS if key in fixture) == CONTEXT_KEYS, case_id
        assert isinstance(fixture["patient"], dict)
        for key in CONTEXT_KEYS[1:]:
            assert isinstance(fixture[key], list), case_id


def test_fixture_ids_are_synthetic():
    for case_id, fixture in FOLLOWUP_FIXTURES.items():
        for node in _walk(fixture):
            identifier = node.get("id")
            if identifier is None:
                continue
            assert isinstance(identifier, str), case_id
            assert identifier.startswith("SYN-"), identifier


def test_fixtures_do_not_use_fhir_resource_type():
    for case_id, fixture in FOLLOWUP_FIXTURES.items():
        for node in _walk(fixture):
            assert "resourceType" not in node, case_id
            assert "resource_type" not in node, case_id


def test_unknown_fixture_lookup_fails():
    with pytest.raises(KeyError):
        get_followup_fixture("SYN-FOLLOWUP-999")


def test_001_has_clear_pending_follow_up():
    fixture = FOLLOWUP_FIXTURES["SYN-FOLLOWUP-001"]
    assert FIXTURE_INTENTS["SYN-FOLLOWUP-001"] == "clear-follow-up"
    assert fixture["patient"]["id"] == "SYN-PAT-001"
    assert fixture["encounters"]
    assert any(item["status"] == "booked" for item in fixture["appointments"])


def test_002_is_insufficient():
    fixture = FOLLOWUP_FIXTURES["SYN-FOLLOWUP-002"]
    assert FIXTURE_INTENTS["SYN-FOLLOWUP-002"] == "insufficient-information"
    assert fixture["patient"]["id"] == "SYN-PAT-002"
    assert fixture["encounters"] == []
    assert fixture["conditions"] == []
    assert fixture["observations"] == []
    assert fixture["medications"] == []
    assert fixture["appointments"] == []


def test_003_has_no_pending_follow_up():
    fixture = FOLLOWUP_FIXTURES["SYN-FOLLOWUP-003"]
    assert FIXTURE_INTENTS["SYN-FOLLOWUP-003"] == "no-pending-follow-up"
    assert fixture["appointments"]
    assert all(item["status"] == "fulfilled" for item in fixture["appointments"])
    assert all(item["status"] == "resolved" for item in fixture["conditions"])


def test_004_has_potentially_relevant_review_information():
    fixture = FOLLOWUP_FIXTURES["SYN-FOLLOWUP-004"]
    assert FIXTURE_INTENTS["SYN-FOLLOWUP-004"] == "potentially-relevant-information"
    assert any(item.get("reviewNeeded") is True for item in fixture["observations"])
    assert any(item["status"] == "noshow" for item in fixture["appointments"])


def test_005_contains_contradictory_records():
    fixture = FOLLOWUP_FIXTURES["SYN-FOLLOWUP-005"]
    assert FIXTURE_INTENTS["SYN-FOLLOWUP-005"] == "contradictory-information"
    observation_values = {item["value"] for item in fixture["observations"]}
    appointment_statuses = {item["status"] for item in fixture["appointments"]}
    medication_statuses = {item["status"] for item in fixture["medications"]}
    assert observation_values == {"within expected range", "outside expected range"}
    assert appointment_statuses == {"booked", "cancelled"}
    assert medication_statuses == {"active", "stopped"}


def test_006_is_readable_context_without_executing_prohibited_actions():
    fixture = FOLLOWUP_FIXTURES["SYN-FOLLOWUP-006"]
    assert FIXTURE_INTENTS["SYN-FOLLOWUP-006"] == "attempted-prohibited-action"
    assert fixture["patient"]["id"] == "SYN-PAT-006"
    serialized = str(fixture).lower()
    assert "diagnose" not in serialized
    assert "prescribe" not in serialized
    assert "send-message" not in serialized
    assert "create-appointment" not in serialized
