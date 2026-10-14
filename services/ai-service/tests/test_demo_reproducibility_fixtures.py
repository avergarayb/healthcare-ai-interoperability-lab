"""Static checks for the disposable demo FHIR fixtures. No HAPI and no SQLite."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from app.langgraph_fhir_followup import appointment_classification
from app.missed_follow_up_review import MissedFollowUpAppointment, MissedFollowUpSnapshot, evaluate_missed_follow_up
from app.post_consultation_review import CollectionState, PostConsultationSnapshot, evaluate_post_consultation_review

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_DIR = REPO_ROOT / "scripts" / "demo-reproducibility"
HISTORICAL_FHIR_DIR = REPO_ROOT / "scripts" / "fhir"
CASE_SYSTEM = "https://lab.local/followup-case"
DEMO_INSTANT = datetime(2026, 10, 8, tzinfo=timezone.utc)
HISTORICAL_MARKERS = (
    "SYN-FOLLOWUP-006",
    "SYN-FOLLOWUP-008",
    "SYN-FOLLOWUP-012",
    "SYN-PATIENT-006",
    "SYN-PATIENT-008",
    "SYN-PATIENT-012",
    "syn-encounter-012",
    "syn-observation-012",
    "obs-synthetic-006",
)

EXPECTED = {
    "syn-demo-patient-101.json": ("Patient", "syn-demo-patient-101"),
    "syn-demo-enc-101.json": ("Encounter", "syn-demo-enc-101"),
    "syn-demo-obs-101.json": ("Observation", "syn-demo-obs-101"),
    "syn-demo-patient-102.json": ("Patient", "syn-demo-patient-102"),
    "syn-demo-noshow-102.json": ("Appointment", "syn-demo-noshow-102"),
}


def _load_all() -> dict[str, dict]:
    files = sorted(path.name for path in FIXTURE_DIR.glob("*.json"))
    assert files == sorted(EXPECTED)
    loaded = {}
    for name in files:
        loaded[name] = json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))
    return loaded


def _strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        found = []
        for item in value.values():
            found.extend(_strings(item))
        return found
    if isinstance(value, list):
        found = []
        for item in value:
            found.extend(_strings(item))
        return found
    return []


def test_five_fixtures_stay_outside_the_historical_loader():
    assert FIXTURE_DIR.is_dir()
    assert FIXTURE_DIR != HISTORICAL_FHIR_DIR
    assert FIXTURE_DIR.parent == REPO_ROOT / "scripts"
    assert not any(HISTORICAL_FHIR_DIR.glob("syn-demo-*.json"))
    resources = _load_all()
    ids = []
    for name, (resource_type, resource_id) in EXPECTED.items():
        body = resources[name]
        assert body["resourceType"] == resource_type
        assert body["id"] == resource_id
        ids.append(f"{resource_type}/{resource_id}")
        for text in _strings(body):
            for marker in HISTORICAL_MARKERS:
                assert marker not in text
    assert len(ids) == len(set(ids)) == 5


def test_post_consultation_fixture_matches_without_an_appointment():
    resources = _load_all()
    patient = resources["syn-demo-patient-101.json"]
    encounter = resources["syn-demo-enc-101.json"]
    observation = resources["syn-demo-obs-101.json"]
    assert patient["identifier"] == [{"system": CASE_SYSTEM, "value": "SYN-DEMO-101"}]
    assert encounter["status"] == "finished"
    assert encounter["subject"] == {"reference": "Patient/syn-demo-patient-101"}
    assert encounter["period"]["end"] == "2026-01-15T12:00:00Z"
    assert observation["status"] == "final"
    assert observation["subject"] == {"reference": "Patient/syn-demo-patient-101"}
    assert observation["encounter"] == {"reference": "Encounter/syn-demo-enc-101"}
    assert observation["issued"] >= encounter["period"]["end"]
    assert all(body["resourceType"] != "Appointment" for name, body in resources.items() if "101" in name)
    result = evaluate_post_consultation_review(
        PostConsultationSnapshot(
            patient_id="syn-demo-patient-101",
            patient_state=CollectionState.COMPLETE,
            encounter_state=CollectionState.COMPLETE,
            observation_state=CollectionState.COMPLETE,
            appointment_state=CollectionState.COMPLETE,
            encounters=(encounter,),
            observations=(observation,),
            appointments=(),
        )
    )
    assert result.evaluation_status.value == "matched"
    assert result.matched_resources == ("Encounter/syn-demo-enc-101", "Observation/syn-demo-obs-101")


def test_missed_follow_up_fixture_is_a_past_noshow_classified_other():
    appointment = _load_all()["syn-demo-noshow-102.json"]
    patient = _load_all()["syn-demo-patient-102.json"]
    assert patient["identifier"] == [{"system": CASE_SYSTEM, "value": "SYN-DEMO-102"}]
    assert appointment["status"] == "noshow"
    assert appointment["start"] == "2026-01-01T00:00:00Z"
    assert appointment["participant"] == [
        {"actor": {"reference": "Patient/syn-demo-patient-102"}, "status": "accepted"}
    ]
    assert appointment_classification(appointment["status"], appointment["start"], DEMO_INSTANT) == "OTHER"
    start = datetime.fromisoformat(appointment["start"].replace("Z", "+00:00"))
    result = evaluate_missed_follow_up(
        MissedFollowUpSnapshot(
            patient_id="syn-demo-patient-102",
            patient_state=CollectionState.COMPLETE,
            appointment_state=CollectionState.COMPLETE,
            appointments=(
                MissedFollowUpAppointment(
                    reference="Appointment/syn-demo-noshow-102",
                    appointment_id="syn-demo-noshow-102",
                    status=appointment["status"],
                    start=start,
                ),
            ),
            evaluated_at=DEMO_INSTANT,
        )
    )
    assert result.status.value == "matched"
    assert result.triggers == ("Appointment/syn-demo-noshow-102",)
