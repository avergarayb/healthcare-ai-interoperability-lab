"""Canonical Task 076 synthetic fixture. Exact equality is required."""

from __future__ import annotations

from typing import Any

from app.experimental_models import ExperimentalSummaryRequest

CANONICAL_FIXTURE: dict[str, Any] = {
    "caseId": "SYN-076-001",
    "patientAgeRange": "50-59",
    "sex": "F",
    "encounterType": "outpatient",
    "observations": [
        {
            "code": "SYN-OBS-001",
            "display": "Synthetic observation A",
            "value": "Synthetic value",
            "unit": "unit",
        },
        {
            "code": "SYN-OBS-002",
            "display": "Synthetic observation B",
            "value": "Synthetic value",
            "unit": "unit",
        },
    ],
    "medications": [
        {
            "code": "SYN-MED-001",
            "display": "Synthetic medication",
        }
    ],
}


def is_canonical_fixture(request: ExperimentalSummaryRequest) -> bool:
    return request.model_dump(by_alias=True) == CANONICAL_FIXTURE
