"""Deterministic reading of LONGITUDINAL_CONTEXT_V1.

Relations require a reference that is present on the resource. A shared time
is not a link. This module does not evaluate a protocol and does not call a model.
"""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.longitudinal_context import LongitudinalContext, LongitudinalFact


SCHEMA = "CLINICAL_CONTEXT_INTELLIGENCE_V1"
_REFERENCE = re.compile(r"^(Encounter|Observation|Appointment)/[A-Za-z0-9.\-]{1,64}$")
_STATUSES = {
    "Encounter": frozenset({"finished", "in-progress", "planned", "cancelled"}),
    "Appointment": frozenset({"booked", "pending", "proposed", "fulfilled", "noshow", "cancelled"}),
    "Observation": frozenset({"final", "preliminary", "corrected"}),
}
_KIND_ORDER = {"confirmed": 0, "incomplete": 1, "unproven": 2}


class ProtocolVerdict(BaseModel):
    """Copy of a protocol result. This model does not calculate that result."""

    model_config = ConfigDict(extra="forbid")

    protocol_id: str
    evaluation_status: str
    reason_codes: list[str] = Field(default_factory=list)
    primary_evidence: list[str] = Field(default_factory=list)


class IntelligenceRelation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["confirmed", "unproven", "incomplete"]
    code: str
    references: list[str]
    evidence: str | None = None


class IntelligenceConflict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    references: list[str]


class OperationalReading(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    source: Literal["protocol", "not_supplied"]
    protocol_id: str | None = Field(default=None, alias="protocolId")
    evaluation_status: str | None = Field(default=None, alias="evaluationStatus")
    reason_codes: list[str] = Field(default_factory=list, alias="reasonCodes")
    primary_evidence: list[str] = Field(default_factory=list, alias="primaryEvidence")


class ClinicalContextIntelligence(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_name: Literal["CLINICAL_CONTEXT_INTELLIGENCE_V1"] = Field(alias="schema", default=SCHEMA)
    case_id: str = Field(alias="caseId")
    patient_id: str | None = Field(default=None, alias="patientId")
    context_status: str = Field(alias="contextStatus")
    truncated: bool = False
    encounters: list[LongitudinalFact] = Field(default_factory=list)
    appointments: list[LongitudinalFact] = Field(default_factory=list)
    observations: list[LongitudinalFact] = Field(default_factory=list)
    relations: list[IntelligenceRelation] = Field(default_factory=list)
    operational: OperationalReading
    complementary_evidence: list[str] = Field(default_factory=list, alias="complementaryEvidence")
    missing: list[str] = Field(default_factory=list)
    conflicts: list[IntelligenceConflict] = Field(default_factory=list)
    provenance: list[dict[str, str | None]] = Field(default_factory=list)


@dataclass(frozen=True)
class _Link:
    kind: Literal["confirmed", "unproven", "incomplete"]
    code: str
    references: tuple[str, ...]
    evidence: str | None = None


def analyze_clinical_context(
    context: LongitudinalContext,
    *,
    protocol: ProtocolVerdict | None = None,
    evaluated_at: datetime | None = None,
) -> ClinicalContextIntelligence:
    """Describe the timeline. The protocol status is copied when one is supplied."""
    encounters = _ordered(context.encounters)
    appointments = _ordered(context.appointments)
    observations = _ordered(context.observations)
    encounter_ids = {item.reference for item in encounters}
    appointment_ids = {item.reference for item in appointments}
    links: list[_Link] = []
    conflicts: list[IntelligenceConflict] = []
    grouped: dict[str, list[LongitudinalFact]] = {}

    for fact in encounters + appointments + observations:
        _status_and_instant(fact, links, conflicts)
    for fact in observations:
        _observation_links(fact, encounter_ids, links, conflicts, grouped)
    for fact in appointments:
        _appointment_links(fact, appointment_ids, links, conflicts, evaluated_at)
    for fact in encounters:
        _unexpected_related(fact, links, conflicts)
    for encounter_reference, grouped_observations in grouped.items():
        encounter = next(item for item in encounters if item.reference == encounter_reference)
        _observation_timing(encounter, grouped_observations, links, conflicts)
        _observation_sequences(encounter_reference, grouped_observations, links)
    _replace_cycles(appointments, conflicts)

    relations = [
        IntelligenceRelation(
            kind=item.kind,
            code=item.code,
            references=list(item.references),
            evidence=item.evidence,
        )
        for item in sorted(links, key=lambda item: (_KIND_ORDER[item.kind], item.code, item.references))
    ]
    missing = _missing(context)
    operational = _operational(protocol)
    primary = set(operational.primary_evidence)
    complementary: list[str] = []
    for relation in relations:
        if relation.kind != "confirmed":
            continue
        for reference in relation.references:
            if reference not in primary and reference not in complementary:
                complementary.append(reference)
    return ClinicalContextIntelligence(
        caseId=context.case_id,
        patientId=context.patient_id,
        contextStatus=context.status,
        truncated=context.truncated,
        encounters=encounters,
        appointments=appointments,
        observations=observations,
        relations=relations,
        operational=operational,
        complementaryEvidence=complementary,
        missing=missing,
        conflicts=sorted(conflicts, key=lambda item: (item.code, item.references)),
        provenance=[
            {"reference": fact.reference, "source": fact.source}
            for fact in encounters + appointments + observations
        ],
    )


def narrative_brief(analysis: ClinicalContextIntelligence) -> dict[str, object]:
    """Bounded facts for a narrative. It omits recorded quantities and protocol arithmetic."""
    confirmed = [
        {"code": item.code, "references": item.references}
        for item in analysis.relations
        if item.kind == "confirmed"
    ][:8]
    brief: dict[str, object] = {
        "schema": SCHEMA,
        "contextStatus": analysis.context_status,
        "truncated": analysis.truncated,
        "operationalStatus": analysis.operational.evaluation_status,
        "reasonCodes": list(analysis.operational.reason_codes)[:8],
        "confirmedRelations": confirmed,
        "missing": list(analysis.missing)[:8],
        "conflicts": [item.code for item in analysis.conflicts][:4],
    }
    encoded = json.dumps(brief, ensure_ascii=False, sort_keys=True)
    if len(encoded) > 3500:
        brief["confirmedRelations"] = confirmed[:4]
        brief["missing"] = list(analysis.missing)[:4]
    return brief


def render_intelligence_html(analysis: ClinicalContextIntelligence) -> str:
    """Spanish section for the existing review page."""
    parts = ['<section class="clinical-context-intelligence"><h2>Análisis de contexto clínico</h2>']
    parts.append("<h3>Datos provenientes del HIS</h3>")
    parts.append(f"<p>Lectura: {_escape(analysis.context_status)}.</p>")
    parts.append(_fact_list("Consultas", analysis.encounters))
    parts.append(_fact_list("Citas", analysis.appointments))
    parts.append(_fact_list("Resultados", analysis.observations))
    parts.append("<h3>Evaluación determinista</h3>")
    parts.append(_operational_html(analysis.operational))
    parts.append(_relation_list("Relaciones confirmadas", analysis.relations, "confirmed"))
    parts.append(_relation_list("Relaciones no demostradas", analysis.relations, "unproven"))
    parts.append(_relation_list("Evidencia incompleta", analysis.relations, "incomplete"))
    parts.append("<h3>Evidencia principal</h3>")
    parts.append(_reference_list(analysis.operational.primary_evidence))
    parts.append("<h3>Evidencia complementaria</h3>")
    parts.append(_reference_list(analysis.complementary_evidence))
    parts.append("<h3>Datos faltantes</h3>")
    parts.append(_reference_list(analysis.missing))
    parts.append("<h3>Conflictos</h3>")
    if analysis.conflicts:
        parts.append("<ul>")
        for conflict in analysis.conflicts:
            refs = ", ".join(conflict.references) if conflict.references else "sin referencia"
            parts.append(f"<li>{_escape(conflict.code)}: {_escape(refs)}</li>")
        parts.append("</ul>")
    else:
        parts.append("<p>No consta.</p>")
    parts.append("<h3>Procedencia</h3><ul>")
    if not analysis.provenance:
        parts.append("<li>No consta.</li>")
    for item in analysis.provenance:
        source = item.get("source") or "procedencia no consta"
        parts.append(f"<li>{_escape(str(item.get('reference')))}: {_escape(str(source))}</li>")
    parts.append("</ul>")
    if analysis.truncated:
        parts.append("<p>El contexto está truncado por el límite de lectura.</p>")
    parts.append(
        "<p>La propuesta de inteligencia artificial, si existe, está en otra sección. "
        "La decisión humana se registra aparte.</p>"
    )
    parts.append("</section>")
    return "".join(parts)


def _ordered(facts: list[LongitudinalFact]) -> list[LongitudinalFact]:
    return sorted(facts, key=lambda item: (item.instant is None, item.instant or "", item.reference))


def _operational(protocol: ProtocolVerdict | None) -> OperationalReading:
    if protocol is None:
        return OperationalReading(source="not_supplied")
    return OperationalReading(
        source="protocol",
        protocolId=protocol.protocol_id,
        evaluationStatus=protocol.evaluation_status,
        reasonCodes=list(protocol.reason_codes),
        primaryEvidence=list(protocol.primary_evidence),
    )


def _missing(context: LongitudinalContext) -> list[str]:
    missing: list[str] = []
    for gap in context.gaps:
        text = gap.code if gap.reference is None else f"{gap.code}:{gap.reference}"
        if text not in missing:
            missing.append(text)
    if context.truncated and "context_truncated" not in missing:
        missing.append("context_truncated")
    return missing


def _status_and_instant(
    fact: LongitudinalFact,
    links: list[_Link],
    conflicts: list[IntelligenceConflict],
) -> None:
    resource_type = fact.reference.split("/", 1)[0]
    allowed = _STATUSES.get(resource_type)
    if fact.status is None:
        links.append(_Link("incomplete", "status_missing", (fact.reference,)))
    elif allowed is not None and fact.status not in allowed:
        conflicts.append(IntelligenceConflict(code="unrecognized_status", references=[fact.reference]))
    if fact.instant is not None and _parsed(fact.instant) is None:
        conflicts.append(IntelligenceConflict(code="instant_unparseable", references=[fact.reference]))
    if fact.end is not None and _parsed(fact.end) is None:
        conflicts.append(IntelligenceConflict(code="instant_unparseable", references=[fact.reference]))


def _observation_links(
    fact: LongitudinalFact,
    encounter_ids: set[str],
    links: list[_Link],
    conflicts: list[IntelligenceConflict],
    grouped: dict[str, list[LongitudinalFact]],
) -> None:
    encounter_links = [item for item in fact.related if item.startswith("Encounter/")]
    if not encounter_links:
        links.append(_Link("unproven", "observation_without_encounter_reference", (fact.reference,)))
    for reference in encounter_links:
        if _REFERENCE.fullmatch(reference) is None:
            conflicts.append(IntelligenceConflict(code="observation_reference_invalid", references=[fact.reference, reference]))
            continue
        if reference not in encounter_ids:
            links.append(
                _Link("incomplete", "observation_encounter_target_absent", (fact.reference, reference), reference)
            )
            continue
        links.append(_Link("confirmed", "observation_encounter", (fact.reference, reference), reference))
        grouped.setdefault(reference, []).append(fact)
    for reference in fact.related:
        if reference.startswith("Encounter/"):
            continue
        conflicts.append(IntelligenceConflict(code="unexpected_relation", references=[fact.reference, reference]))


def _appointment_links(
    fact: LongitudinalFact,
    appointment_ids: set[str],
    links: list[_Link],
    conflicts: list[IntelligenceConflict],
    evaluated_at: datetime | None,
) -> None:
    for reference in fact.related:
        if not reference.startswith("Appointment/"):
            conflicts.append(IntelligenceConflict(code="unexpected_relation", references=[fact.reference, reference]))
            continue
        if reference == fact.reference:
            conflicts.append(IntelligenceConflict(code="appointment_replaces_self", references=[fact.reference]))
            continue
        if _REFERENCE.fullmatch(reference) is None:
            conflicts.append(IntelligenceConflict(code="appointment_reference_invalid", references=[fact.reference, reference]))
            continue
        if reference not in appointment_ids:
            links.append(
                _Link("incomplete", "appointment_replaces_target_absent", (fact.reference, reference), reference)
            )
            continue
        links.append(_Link("confirmed", "appointment_replaces", (fact.reference, reference), reference))
    if fact.status != "booked":
        return
    start = _parsed(fact.instant)
    if fact.instant is None or start is None:
        links.append(_Link("incomplete", "booked_start_missing", (fact.reference,)))
        return
    if evaluated_at is None:
        links.append(_Link("unproven", "appointment_time_not_evaluated", (fact.reference,), fact.instant))
        return
    if start >= evaluated_at:
        links.append(_Link("confirmed", "future_booked_appointment", (fact.reference,), fact.instant))


def _unexpected_related(
    fact: LongitudinalFact,
    links: list[_Link],
    conflicts: list[IntelligenceConflict],
) -> None:
    del links
    for reference in fact.related:
        conflicts.append(IntelligenceConflict(code="unexpected_relation", references=[fact.reference, reference]))


def _observation_timing(
    encounter: LongitudinalFact,
    observations: list[LongitudinalFact],
    links: list[_Link],
    conflicts: list[IntelligenceConflict],
) -> None:
    start = _parsed(encounter.instant)
    end = _parsed(encounter.end)
    for observation in observations:
        issued = _parsed(observation.instant)
        references = (observation.reference, encounter.reference)
        if issued is None or (encounter.end is None and encounter.instant is None):
            links.append(_Link("incomplete", "observation_timing_incomplete", references))
            continue
        if start is not None and issued < start:
            conflicts.append(
                IntelligenceConflict(code="observation_issued_before_encounter_start", references=list(references))
            )
            continue
        if end is None:
            links.append(_Link("incomplete", "observation_timing_end_missing", references, encounter.reference))
            continue
        code = "observation_issued_after_encounter_end" if issued >= end else "observation_issued_before_encounter_end"
        links.append(_Link("confirmed", code, references, observation.instant))


def _observation_sequences(
    encounter_reference: str,
    observations: list[LongitudinalFact],
    links: list[_Link],
) -> None:
    dated = [(observation, _parsed(observation.instant)) for observation in observations]
    preliminary = [item for item in dated if item[0].status == "preliminary"]
    if not preliminary:
        return
    if any(instant is None for _, instant in dated):
        links.append(
            _Link(
                "incomplete",
                "observation_sequence_undated",
                tuple(item.reference for item in observations) + (encounter_reference,),
                encounter_reference,
            )
        )
        return
    for earlier, earlier_instant in preliminary:
        if earlier_instant is None:
            continue
        for later_status, code in (("final", "preliminary_then_final"), ("corrected", "preliminary_then_corrected")):
            candidates = [
                item
                for item, instant in dated
                if item.status == later_status and instant is not None and instant >= earlier_instant
            ]
            if not candidates:
                continue
            chosen = sorted(candidates, key=lambda item: (item.instant or "", item.reference))[0]
            links.append(
                _Link(
                    "confirmed",
                    code,
                    (earlier.reference, chosen.reference, encounter_reference),
                    encounter_reference,
                )
            )


def _replace_cycles(appointments: list[LongitudinalFact], conflicts: list[IntelligenceConflict]) -> None:
    replaces = {}
    for fact in appointments:
        targets = [item for item in fact.related if item.startswith("Appointment/") and item != fact.reference]
        if len(targets) == 1 and _REFERENCE.fullmatch(targets[0]):
            replaces[fact.reference] = targets[0]
    seen: set[str] = set()
    for start in replaces:
        if start in seen:
            continue
        path = [start]
        current = start
        while current in replaces and replaces[current] not in path:
            current = replaces[current]
            path.append(current)
        if current in replaces and replaces[current] in path:
            cycle = path[path.index(replaces[current]) :]
            if len(cycle) > 1:
                conflicts.append(IntelligenceConflict(code="appointment_replaces_cycle", references=cycle))
                seen.update(cycle)


def _parsed(value: str | None) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed


def _fact_list(title: str, facts: list[LongitudinalFact]) -> str:
    if not facts:
        return f"<h4>{title}</h4><p>No consta.</p>"
    parts = [f"<h4>{title}</h4><ul>"]
    for fact in facts:
        when = fact.instant or "fecha no consta"
        status = fact.status or "estado no consta"
        parts.append(f"<li>{_escape(fact.reference)}; {_escape(status)}; {_escape(when)}</li>")
    parts.append("</ul>")
    return "".join(parts)


def _operational_html(operational: OperationalReading) -> str:
    if operational.source == "not_supplied":
        return "<p>No se recibió el resultado del protocolo. Esta vista no lo calcula.</p>"
    reasons = ", ".join(operational.reason_codes) if operational.reason_codes else "sin código"
    return (
        f"<p>Protocolo {_escape(operational.protocol_id or '')}. "
        f"Resultado copiado: {_escape(operational.evaluation_status or '')}. "
        f"Motivos: {_escape(reasons)}. Esta vista no vuelve a ejecutar la regla.</p>"
    )


def _relation_list(title: str, relations: list[IntelligenceRelation], kind: str) -> str:
    selected = [item for item in relations if item.kind == kind]
    parts = [f"<h4>{title}</h4>"]
    if not selected:
        parts.append("<p>No consta.</p>")
        return "".join(parts)
    parts.append("<ul>")
    for item in selected:
        refs = ", ".join(item.references)
        parts.append(f"<li>{_escape(item.code)}: {_escape(refs)}</li>")
    parts.append("</ul>")
    return "".join(parts)


def _reference_list(values: list[str]) -> str:
    if not values:
        return "<p>No consta.</p>"
    return "<ul>" + "".join(f"<li>{_escape(value)}</li>" for value in values) + "</ul>"


def _escape(value: str) -> str:
    return html.escape(value, quote=True)
