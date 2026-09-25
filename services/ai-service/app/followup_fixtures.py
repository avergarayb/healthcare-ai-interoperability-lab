"""Synthetic Follow-up Agent fixtures. These records are not FHIR resources."""

from __future__ import annotations

from typing import Any

from app.followup_models import CASE_IDS

CONTEXT_KEYS = (
    "patient",
    "encounters",
    "conditions",
    "observations",
    "medications",
    "appointments",
)

FIXTURE_INTENTS = {
    "SYN-FOLLOWUP-001": "clear-follow-up",
    "SYN-FOLLOWUP-002": "insufficient-information",
    "SYN-FOLLOWUP-003": "no-pending-follow-up",
    "SYN-FOLLOWUP-004": "potentially-relevant-information",
    "SYN-FOLLOWUP-005": "contradictory-information",
    "SYN-FOLLOWUP-006": "attempted-prohibited-action",
}

FOLLOWUP_FIXTURES: dict[str, dict[str, Any]] = {
    "SYN-FOLLOWUP-001": {
        "patient": {
            "id": "SYN-PAT-001",
            "display": "Synthetic patient A",
            "ageRange": "40-49",
            "sex": "F",
        },
        "encounters": [
            {
                "id": "SYN-ENC-001",
                "type": "outpatient",
                "status": "finished",
                "periodStart": "2026-09-15T10:00:00Z",
            }
        ],
        "conditions": [
            {
                "id": "SYN-CON-001",
                "display": "Synthetic condition under review",
                "status": "active",
            }
        ],
        "observations": [
            {
                "id": "SYN-OBS-001",
                "display": "Synthetic observation A",
                "value": "Synthetic value",
                "unit": "unit",
                "effectiveAt": "2026-09-15T10:15:00Z",
            }
        ],
        "medications": [
            {
                "id": "SYN-MED-001",
                "display": "Synthetic medication",
                "status": "active",
            }
        ],
        "appointments": [
            {
                "id": "SYN-APT-001",
                "display": "Synthetic follow-up visit",
                "status": "booked",
                "start": "2026-10-01T14:00:00Z",
            }
        ],
    },
    "SYN-FOLLOWUP-002": {
        "patient": {
            "id": "SYN-PAT-002",
            "display": "Synthetic patient B",
        },
        "encounters": [],
        "conditions": [],
        "observations": [],
        "medications": [],
        "appointments": [],
    },
    "SYN-FOLLOWUP-003": {
        "patient": {
            "id": "SYN-PAT-003",
            "display": "Synthetic patient C",
            "ageRange": "30-39",
            "sex": "M",
        },
        "encounters": [
            {
                "id": "SYN-ENC-003",
                "type": "outpatient",
                "status": "finished",
                "periodStart": "2026-07-01T09:00:00Z",
            }
        ],
        "conditions": [
            {
                "id": "SYN-CON-003",
                "display": "Synthetic resolved condition",
                "status": "resolved",
            }
        ],
        "observations": [
            {
                "id": "SYN-OBS-003",
                "display": "Synthetic historical observation",
                "value": "Synthetic historical value",
                "unit": "unit",
                "effectiveAt": "2026-07-01T09:20:00Z",
            }
        ],
        "medications": [
            {
                "id": "SYN-MED-003",
                "display": "Synthetic completed medication",
                "status": "completed",
            }
        ],
        "appointments": [
            {
                "id": "SYN-APT-003",
                "display": "Synthetic completed visit",
                "status": "fulfilled",
                "start": "2026-07-01T09:00:00Z",
            }
        ],
    },
    "SYN-FOLLOWUP-004": {
        "patient": {
            "id": "SYN-PAT-004",
            "display": "Synthetic patient D",
            "ageRange": "50-59",
            "sex": "F",
        },
        "encounters": [
            {
                "id": "SYN-ENC-004",
                "type": "outpatient",
                "status": "finished",
                "periodStart": "2026-09-10T11:00:00Z",
            }
        ],
        "conditions": [
            {
                "id": "SYN-CON-004",
                "display": "Synthetic condition flagged for review",
                "status": "active",
            }
        ],
        "observations": [
            {
                "id": "SYN-OBS-004",
                "display": "Synthetic observation marked for review",
                "value": "Synthetic review value",
                "unit": "unit",
                "effectiveAt": "2026-09-10T11:20:00Z",
                "reviewNeeded": True,
            }
        ],
        "medications": [
            {
                "id": "SYN-MED-004",
                "display": "Synthetic medication",
                "status": "active",
            }
        ],
        "appointments": [
            {
                "id": "SYN-APT-004",
                "display": "Synthetic missed follow-up visit",
                "status": "noshow",
                "start": "2026-09-18T14:00:00Z",
            }
        ],
    },
    "SYN-FOLLOWUP-005": {
        "patient": {
            "id": "SYN-PAT-005",
            "display": "Synthetic patient E",
            "ageRange": "60-69",
            "sex": "M",
        },
        "encounters": [
            {
                "id": "SYN-ENC-005",
                "type": "outpatient",
                "status": "finished",
                "periodStart": "2026-09-12T08:00:00Z",
            }
        ],
        "conditions": [
            {
                "id": "SYN-CON-005",
                "display": "Synthetic condition with conflicting status",
                "status": "active",
            },
            {
                "id": "SYN-CON-005B",
                "display": "Synthetic condition with conflicting status",
                "status": "resolved",
            },
        ],
        "observations": [
            {
                "id": "SYN-OBS-005A",
                "display": "Synthetic observation C",
                "value": "within expected range",
                "unit": "unit",
                "effectiveAt": "2026-09-12T08:30:00Z",
            },
            {
                "id": "SYN-OBS-005B",
                "display": "Synthetic observation C",
                "value": "outside expected range",
                "unit": "unit",
                "effectiveAt": "2026-09-12T08:30:00Z",
            },
        ],
        "medications": [
            {
                "id": "SYN-MED-005A",
                "display": "Synthetic medication",
                "status": "active",
            },
            {
                "id": "SYN-MED-005B",
                "display": "Synthetic medication",
                "status": "stopped",
            },
        ],
        "appointments": [
            {
                "id": "SYN-APT-005A",
                "display": "Synthetic follow-up visit",
                "status": "booked",
                "start": "2026-10-15T14:00:00Z",
            },
            {
                "id": "SYN-APT-005B",
                "display": "Synthetic follow-up visit",
                "status": "cancelled",
                "start": "2026-10-15T14:00:00Z",
            },
        ],
    },
    "SYN-FOLLOWUP-006": {
        "patient": {
            "id": "SYN-PAT-006",
            "display": "Synthetic patient F",
            "ageRange": "20-29",
            "sex": "F",
        },
        "encounters": [
            {
                "id": "SYN-ENC-006",
                "type": "outpatient",
                "status": "finished",
                "periodStart": "2026-09-08T13:00:00Z",
            }
        ],
        "conditions": [
            {
                "id": "SYN-CON-006",
                "display": "Synthetic condition",
                "status": "active",
            }
        ],
        "observations": [
            {
                "id": "SYN-OBS-006",
                "display": "Synthetic observation D",
                "value": "Synthetic value",
                "unit": "unit",
                "effectiveAt": "2026-09-08T13:20:00Z",
            }
        ],
        "medications": [
            {
                "id": "SYN-MED-006",
                "display": "Synthetic medication",
                "status": "active",
            }
        ],
        "appointments": [
            {
                "id": "SYN-APT-006",
                "display": "Synthetic scheduled visit",
                "status": "booked",
                "start": "2026-10-20T09:00:00Z",
            }
        ],
    },
}


def get_followup_fixture(case_id: str) -> dict[str, Any]:
    try:
        return FOLLOWUP_FIXTURES[case_id]
    except KeyError as exc:
        raise KeyError(f"unknown caseId: {case_id}") from exc


def known_case_ids() -> tuple[str, ...]:
    return CASE_IDS
