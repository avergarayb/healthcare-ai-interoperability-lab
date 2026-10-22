"""Operational appointment labels. These tests do not call a model."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.langgraph_fhir_client import PATIENT_ID, synthetic_appointment
from app.langgraph_fhir_followup import (
    CANCELLED,
    NONE,
    OTHER,
    PAST,
    UPCOMING_CONFIRMED,
    UPCOMING_UNCONFIRMED,
    _appointment_refs,
    appointment_classification,
    appointment_facts,
)


NOW = datetime(2026, 9, 28, tzinfo=timezone.utc)
FUTURE = "2027-03-15T15:00:00Z"
PAST_START = "2020-01-15T15:00:00Z"
FIXTURES = Path(__file__).resolve().parents[3] / "scripts" / "fhir"


@pytest.mark.parametrize(
    ("status", "start", "expected"),
    [
        ("booked", FUTURE, UPCOMING_CONFIRMED),
        ("booked", "2026-09-28T00:00:00Z", UPCOMING_CONFIRMED),
        ("booked", "2027-03-15T15:00:00", UPCOMING_CONFIRMED),
        ("pending", FUTURE, UPCOMING_UNCONFIRMED),
        ("proposed", FUTURE, UPCOMING_UNCONFIRMED),
        ("cancelled", FUTURE, CANCELLED),
        ("cancelled", PAST_START, CANCELLED),
        ("cancelled", None, CANCELLED),
        ("cancelled", "not-a-date", CANCELLED),
        ("booked", PAST_START, PAST),
        ("fulfilled", PAST_START, PAST),
        ("noshow", PAST_START, OTHER),
        ("noshow", FUTURE, OTHER),
        ("entered-in-error", PAST_START, OTHER),
        ("arrived", FUTURE, OTHER),
        ("arrived", PAST_START, OTHER),
        ("checked-in", FUTURE, OTHER),
        ("waitlist", FUTURE, OTHER),
        ("waitlist", None, OTHER),
        ("booked", None, OTHER),
        ("booked", "not-a-date", OTHER),
        ("pending", PAST_START, OTHER),
        ("proposed", None, OTHER),
        ("fulfilled", FUTURE, OTHER),
        ("fulfilled", None, OTHER),
    ],
)
def test_appointment_classification(status: str, start: str | None, expected: str):
    assert appointment_classification(status, start, NOW) == expected


def test_empty_search_is_none_and_has_no_appointment_id():
    facts = appointment_facts(
        {"resourceType": "Bundle", "type": "searchset", "entry": []},
        PATIENT_ID,
        NOW,
    )
    assert facts["classifications"] == [NONE]
    assert facts["appointments"] == []
    assert _appointment_refs(facts["appointments"]) == []


def test_another_patients_appointment_is_omitted():
    foreign = synthetic_appointment(
        appointment_id="appointment-other",
        status="booked",
        start=FUTURE,
        patient_id="patient-001",
    )
    facts = appointment_facts(_bundle([foreign]), PATIENT_ID, NOW)
    assert facts["classifications"] == [NONE]
    assert facts["appointments"] == []


def test_cancelled_and_past_appointments_stay_visible():
    cancelled = synthetic_appointment(
        appointment_id="appointment-synthetic-cancelled-001",
        status="cancelled",
        start=FUTURE,
        patient_id=PATIENT_ID,
    )
    past = synthetic_appointment(
        appointment_id="appointment-synthetic-past-001",
        status="booked",
        start=PAST_START,
        patient_id=PATIENT_ID,
    )
    facts = appointment_facts(_bundle([past, cancelled]), PATIENT_ID, NOW)
    assert facts["classifications"] == [CANCELLED, PAST]
    assert _appointment_refs(facts["appointments"]) == [
        "Appointment/appointment-synthetic-past-001",
        "Appointment/appointment-synthetic-cancelled-001",
    ]


def test_synthetic_appointment_files_keep_states_on_separate_patients():
    booked = json.loads((FIXTURES / "appointment-synthetic-001.json").read_text(encoding="utf-8"))
    pending = json.loads((FIXTURES / "syn-appointment-pending-001.json").read_text(encoding="utf-8"))
    cancelled = json.loads((FIXTURES / "syn-appointment-cancelled-001.json").read_text(encoding="utf-8"))
    past = json.loads((FIXTURES / "syn-appointment-past-001.json").read_text(encoding="utf-8"))
    none_patient = json.loads((FIXTURES / "syn-patient-006.json").read_text(encoding="utf-8"))
    appointments = [booked, pending, cancelled, past]
    assert _label(booked) == UPCOMING_CONFIRMED
    assert _label(pending) == UPCOMING_UNCONFIRMED
    assert _label(cancelled) == CANCELLED
    assert _label(past) == PAST
    patients = {_participant(item) for item in appointments}
    assert patients == {
        "Patient/SYN-PATIENT-001",
        "Patient/SYN-PATIENT-002",
        "Patient/SYN-PATIENT-003",
        "Patient/SYN-PATIENT-004",
    }
    assert all("patient-001" not in _participant(item) for item in appointments)
    assert none_patient["id"] == "SYN-PATIENT-006"
    assert not any(_participant(item) == "Patient/SYN-PATIENT-006" for item in appointments)


def _bundle(resources: list[dict]) -> dict:
    return {"resourceType": "Bundle", "type": "searchset", "entry": [{"resource": item} for item in resources]}


def _participant(resource: dict) -> str:
    return resource["participant"][0]["actor"]["reference"]


def _label(resource: dict) -> str:
    patient_id = _participant(resource).removeprefix("Patient/")
    facts = appointment_facts(_bundle([resource]), patient_id, NOW)
    assert facts["classifications"] != [NONE]
    return facts["appointments"][0]["classification"]
