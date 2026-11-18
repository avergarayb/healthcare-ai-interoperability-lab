"""Closed dated pairs. They are not part of the summary observation list."""
from dataclasses import dataclass

from app.enterprise_llm_providers.errors import ProviderError


OPERATION_ID = "longitudinal-lab-comparison-v1"
TAG = "longitudinal-series"
METHOD_SYSTEM = "https://lab.local/jurisdiction/method"
METHOD_CODE = "venous-draw-v1"


@dataclass(frozen=True, slots=True)
class SeriesPoint:
    resource_id: str
    value: str
    effective: str


@dataclass(frozen=True, slots=True)
class LongitudinalSeries:
    code: str
    unit: str
    specimen: str
    method_system: str
    method_code: str
    prior: SeriesPoint
    recent: SeriesPoint
    authorization_id: str
    policy_ref: str


def _series(code, unit, specimen, prior, recent, authorization_id, policy_ref):
    return LongitudinalSeries(
        code, unit, specimen, METHOD_SYSTEM, METHOD_CODE, prior, recent, authorization_id, policy_ref)


PERU = _series(
    "718-7", "g/dL", "Specimen/pe-spec-718-7",
    SeriesPoint("pe-long-718-7-20261001", "12.8", "2026-10-01T08:00:00Z"),
    SeriesPoint("pe-long-718-7-20261115", "13.4", "2026-11-15T08:00:00Z"),
    "pe-longitudinal-001", "pe-longitudinal-lab-policy-v1")
SPAIN = _series(
    "2345-7", "mg/dL", "Specimen/es-spec-2345-7",
    SeriesPoint("es-long-2345-7-20261001", "95", "2026-10-01T08:00:00Z"),
    SeriesPoint("es-long-2345-7-20261115", "90", "2026-11-15T08:00:00Z"),
    "es-longitudinal-001", "es-longitudinal-lab-policy-v1")
SERIES = {"pe-lab-demo-v1": PERU, "es-lab-demo-v1": SPAIN}


def series_for(profile):
    found = SERIES.get(getattr(profile, "profile_id", None))
    if found is None:
        raise ProviderError("profile_unknown")
    return found
