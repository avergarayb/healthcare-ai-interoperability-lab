"""Bounded timeline for one authorized case, read only through Clinical Read.

This module does not evaluate a protocol, call a model, or open Mini HIS storage.
A missing date stays missing. A recorded quantity is copied, not interpreted.
"""

from __future__ import annotations

import html
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from app.langgraph_fhir_client import BoundedSearchResult, BoundedSearchStatus
from app.langgraph_fhir_followup import case_resolution_search_path
from app.post_consultation_review import validated_fhir_id


SCHEMA = "LONGITUDINAL_CONTEXT_V1"
MAX_ENCOUNTERS = 12
MAX_OBSERVATIONS = 24
MAX_APPOINTMENTS = 12
_ENCOUNTER_STATUSES = ("finished", "in-progress", "planned", "cancelled")
_OBSERVATION_STATUSES = ("final", "preliminary", "corrected")
_REPLACES = "https://lab.local/mini-his/StructureDefinition/replaces-appointment"


class _Reader(Protocol):
    def search(self, path: str, expected_resource_type: str) -> BoundedSearchResult: ...


class LongitudinalFact(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    reference: str
    status: str | None = None
    instant: str | None = None
    related: list[str] = Field(default_factory=list)
    source: str | None = None
    recorded_value: str | None = Field(default=None, alias="recordedValue")


class LongitudinalGap(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    reference: str | None = None


class LongitudinalContext(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_name: Literal["LONGITUDINAL_CONTEXT_V1"] = Field(alias="schema", default=SCHEMA)
    case_id: str = Field(alias="caseId")
    patient_id: str | None = Field(default=None, alias="patientId")
    status: Literal["complete", "partial", "unavailable"]
    encounters: list[LongitudinalFact] = Field(default_factory=list)
    appointments: list[LongitudinalFact] = Field(default_factory=list)
    observations: list[LongitudinalFact] = Field(default_factory=list)
    gaps: list[LongitudinalGap] = Field(default_factory=list)
    truncated: bool = False


def build_longitudinal_context(reader: _Reader, case_id: str) -> LongitudinalContext:
    """Read the patient timeline. Protocol status is not decided here."""
    if not isinstance(case_id, str) or not case_id.strip():
        return _unavailable(case_id or "", "authorized_patient_missing")
    patient_result = reader.search(case_resolution_search_path(case_id), "Patient")
    if patient_result.status is not BoundedSearchStatus.COMPLETE or len(patient_result.resources) != 1:
        code = "acquisition_unavailable" if patient_result.status is BoundedSearchStatus.FAILED else "authorized_patient_missing"
        return _unavailable(case_id, code)
    patient = patient_result.resources[0]
    patient_id = patient.get("id") if isinstance(patient, dict) else None
    if not isinstance(patient_id, str) or validated_fhir_id(patient_id) is None:
        return _unavailable(case_id, "authorized_patient_missing")

    gaps: list[LongitudinalGap] = []
    truncated = False
    failed = False
    encounters, truncated, failed = _collect(
        reader,
        "Encounter",
        [f"Encounter?patient={patient_id}&status={status}" for status in _ENCOUNTER_STATUSES],
        MAX_ENCOUNTERS,
        gaps,
        truncated,
        failed,
    )
    observations, truncated, failed = _collect(
        reader,
        "Observation",
        [f"Observation?subject=Patient/{patient_id}&status={status}" for status in _OBSERVATION_STATUSES],
        MAX_OBSERVATIONS,
        gaps,
        truncated,
        failed,
    )
    appointments, truncated, failed = _collect(
        reader,
        "Appointment",
        [f"Appointment?patient={patient_id}"],
        MAX_APPOINTMENTS,
        gaps,
        truncated,
        failed,
    )
    return LongitudinalContext(
        caseId=case_id,
        patientId=patient_id,
        status="partial" if failed or truncated else "complete",
        encounters=encounters,
        observations=observations,
        appointments=appointments,
        gaps=gaps,
        truncated=truncated,
    )


def render_timeline_html(context: LongitudinalContext) -> str:
    """Spanish section for the existing review page. It does not give clinical advice."""
    parts = ['<section><h2>Historial longitudinal</h2>']
    parts.append(f"<p>Estado de la lectura: {_escape(context.status)}.</p>")
    if context.patient_id:
        parts.append(f"<p>Paciente: {_escape(context.patient_id)}.</p>")
    else:
        parts.append("<p>Paciente: No consta.</p>")
    parts.append(_facts_html("Consultas", context.encounters))
    parts.append(_facts_html("Citas", context.appointments))
    parts.append(_facts_html("Resultados", context.observations))
    if context.gaps:
        parts.append("<h3>Datos ausentes o incompletos</h3><ul>")
        for gap in context.gaps:
            where = f" ({gap.reference})" if gap.reference else ""
            parts.append(f"<li>{_escape(gap.code)}{_escape(where)}</li>")
        parts.append("</ul>")
    if context.truncated:
        parts.append("<p>La lectura está limitada y no incluye todo el historial.</p>")
    parts.append("</section>")
    return "".join(parts)


def _unavailable(case_id: str, code: str) -> LongitudinalContext:
    return LongitudinalContext(
        caseId=case_id,
        status="unavailable",
        gaps=[LongitudinalGap(code=code)],
    )


def _collect(
    reader: _Reader,
    resource_type: str,
    paths: list[str],
    limit: int,
    gaps: list[LongitudinalGap],
    truncated: bool,
    failed: bool,
) -> tuple[list[LongitudinalFact], bool, bool]:
    facts: list[LongitudinalFact] = []
    seen: set[str] = set()
    for path in paths:
        result = reader.search(path, resource_type)
        if result.status is BoundedSearchStatus.FAILED:
            failed = True
            gaps.append(LongitudinalGap(code=f"{resource_type.lower()}_search_unavailable"))
            continue
        if result.status is BoundedSearchStatus.INCOMPLETE_LIMIT:
            truncated = True
            gaps.append(LongitudinalGap(code="bounded_search_incomplete"))
        for resource in result.resources:
            fact = _fact(resource, resource_type, gaps)
            if fact is None or fact.reference in seen:
                continue
            seen.add(fact.reference)
            facts.append(fact)
    facts.sort(key=lambda item: (item.instant is None, item.instant or "", item.reference))
    if len(facts) > limit:
        truncated = True
        gaps.append(LongitudinalGap(code="context_limit_applied"))
        facts = facts[:limit]
    return facts, truncated, failed


def _fact(resource: dict, resource_type: str, gaps: list[LongitudinalGap]) -> LongitudinalFact | None:
    if resource.get("resourceType") != resource_type:
        return None
    resource_id = resource.get("id")
    if not isinstance(resource_id, str) or validated_fhir_id(resource_id) is None:
        return None
    reference = f"{resource_type}/{resource_id}"
    status = resource.get("status") if isinstance(resource.get("status"), str) else None
    instant = _instant(resource, resource_type)
    related = _related(resource)
    source = _source(resource)
    if source is None:
        gaps.append(LongitudinalGap(code="provenance_missing", reference=reference))
    if resource_type == "Encounter" and status == "finished" and not _nested(resource, "period", "end"):
        gaps.append(LongitudinalGap(code="encounter_end_missing", reference=reference))
    if resource_type == "Observation" and instant is None:
        gaps.append(LongitudinalGap(code="observation_issued_missing", reference=reference))
    if resource_type == "Appointment" and instant is None:
        gaps.append(LongitudinalGap(code="appointment_start_missing", reference=reference))
    return LongitudinalFact(
        reference=reference,
        status=status,
        instant=instant,
        related=related,
        source=source,
        recordedValue=_recorded_value(resource) if resource_type == "Observation" else None,
    )


def _instant(resource: dict, resource_type: str) -> str | None:
    if resource_type == "Encounter":
        return _text(_nested(resource, "period", "start"))
    if resource_type == "Observation":
        return _text(resource.get("issued"))
    return _text(resource.get("start"))


def _related(resource: dict) -> list[str]:
    related: list[str] = []
    encounter = resource.get("encounter")
    reference = encounter.get("reference") if isinstance(encounter, dict) else None
    if isinstance(reference, str) and reference:
        related.append(reference)
    extensions = resource.get("extension")
    if isinstance(extensions, list):
        for item in extensions:
            if not isinstance(item, dict) or item.get("url") != _REPLACES:
                continue
            value = item.get("valueReference")
            target = value.get("reference") if isinstance(value, dict) else None
            if isinstance(target, str) and target:
                related.append(target)
    return related


def _source(resource: dict) -> str | None:
    meta = resource.get("meta")
    source = meta.get("source") if isinstance(meta, dict) else None
    return source if isinstance(source, str) and source.strip() else None


def _recorded_value(resource: dict) -> str | None:
    quantity = resource.get("valueQuantity")
    if isinstance(quantity, dict) and isinstance(quantity.get("value"), (int, float)):
        unit = quantity.get("unit")
        text = str(quantity["value"])
        if isinstance(unit, str) and unit.strip():
            text = f"{text} {unit.strip()}"
        return text[:80]
    value = resource.get("valueString")
    if isinstance(value, str) and value.strip():
        return value.strip()[:80]
    return None


def _nested(resource: dict, field: str, child: str) -> object:
    parent = resource.get(field)
    if not isinstance(parent, dict):
        return None
    return parent.get(child)


def _text(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _facts_html(title: str, facts: list[LongitudinalFact]) -> str:
    parts = [f"<h3>{title}</h3>"]
    if not facts:
        parts.append("<p>No consta.</p>")
        return "".join(parts)
    parts.append("<ul>")
    for fact in facts:
        when = fact.instant or "fecha no consta"
        status = fact.status or "estado no consta"
        source = fact.source or "procedencia no consta"
        related = ", ".join(fact.related) if fact.related else "sin relación adicional"
        value = f" Valor registrado: {fact.recorded_value}." if fact.recorded_value else ""
        parts.append(
            "<li>"
            f"{_escape(fact.reference)}; estado {_escape(status)}; "
            f"{_escape(when)}; {_escape(related)}; procedencia {_escape(source)}."
            f"{_escape(value)}"
            "</li>"
        )
    parts.append("</ul>")
    return "".join(parts)


def _escape(value: str) -> str:
    return html.escape(value, quote=True)
