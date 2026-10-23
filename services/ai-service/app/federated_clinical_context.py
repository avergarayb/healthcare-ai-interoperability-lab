"""Adapt a Java federation envelope to the longitudinal context the workflow already stores.

Resources stay separate when their code and value match. A missing resource is a gap,
not a normal result. This module does not call a source.
"""

from __future__ import annotations

from app.longitudinal_context import (
    SCHEMA,
    LongitudinalContext,
    LongitudinalFact,
    LongitudinalGap,
)
from app.post_consultation_review import validated_fhir_id


_TIMELINE_TYPES = frozenset({"Encounter", "Observation", "Appointment"})
_REPORT_TYPES = frozenset({"DiagnosticReport", "ServiceRequest"})
_FAILURE_OUTCOMES = frozenset({
    "identity_unresolved",
    "unavailable",
    "connector_unavailable",
    "not_registered",
    "capability_unsupported",
    "limit_reached",
})


def adapt_federation_envelope(envelope: dict, case_id: str) -> tuple[LongitudinalContext, dict]:
    """Return the timeline and a projection that keeps source outcomes and provenance."""
    status = envelope.get("status")
    sources = _sources(envelope)
    warnings = _warnings(status, sources)
    if status == "failed":
        context = LongitudinalContext(
            caseId=case_id,
            status="unavailable",
            gaps=[LongitudinalGap(code=code) for code in warnings],
        )
        return context, _projection(context, envelope, sources, warnings, [], [])
    facts, reports, gaps, rows = _entries(envelope.get("entries") or [])
    gaps.extend(LongitudinalGap(code=code) for code in warnings if not code.startswith("no_resources:"))
    partial = status == "partial" or any(gap.code == "provenance_missing" for gap in gaps)
    context = LongitudinalContext(
        caseId=case_id,
        patientId=_caller_patient_id(envelope, facts),
        status="partial" if partial else "complete",
        encounters=[item for item in facts if item.reference.startswith("Encounter/")],
        observations=[item for item in facts if item.reference.startswith("Observation/")],
        appointments=[item for item in facts if item.reference.startswith("Appointment/")],
        gaps=gaps,
        truncated=bool(envelope.get("truncated")),
    )
    return context, _projection(context, envelope, sources, warnings, rows, reports)


def failure_projection(code: str) -> dict:
    """Context stored when Java denies or cannot complete the query. No clinical entries."""
    return {
        "schema": SCHEMA,
        "contextStatus": "unavailable",
        "truncated": False,
        "patientReference": None,
        "counts": {"encounters": 0, "observations": 0, "appointments": 0, "reports": 0},
        "federation": {
            "status": "failed",
            "sources": [],
            "warnings": [code],
            "resources": [],
            "reports": [],
        },
    }


def project_context(context: LongitudinalContext, projection: dict) -> dict:
    patient = f"Patient/{context.patient_id}" if context.patient_id else None
    return {
        "schema": SCHEMA,
        "contextStatus": context.status,
        "truncated": bool(context.truncated),
        "patientReference": patient,
        "counts": {
            "encounters": len(context.encounters),
            "observations": len(context.observations),
            "appointments": len(context.appointments),
            "reports": len(projection.get("reports") or []),
        },
        "federation": {
            "status": projection.get("status"),
            "sources": list(projection.get("sources") or []),
            "warnings": list(projection.get("warnings") or []),
            "resources": list(projection.get("resources") or []),
            "reports": list(projection.get("reports") or []),
            "callerSystem": projection.get("callerSystem"),
        },
    }


def _entries(entries: list) -> tuple[list[LongitudinalFact], list[dict], list[LongitudinalGap], list[dict]]:
    facts: list[LongitudinalFact] = []
    reports: list[dict] = []
    gaps: list[LongitudinalGap] = []
    rows: list[dict] = []
    seen: set[str] = set()
    provenance: set[str] = set()
    references: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            gaps.append(LongitudinalGap(code="federation_entry_invalid"))
            continue
        resource = entry.get("resource")
        if not isinstance(resource, dict):
            gaps.append(LongitudinalGap(code="federation_entry_invalid"))
            continue
        resource_type = resource.get("resourceType")
        resource_id = resource.get("id")
        source_key = entry.get("sourceKey") if isinstance(entry.get("sourceKey"), str) else ""
        if not isinstance(resource_type, str) or validated_fhir_id(resource_id) is None or not source_key:
            gaps.append(LongitudinalGap(code="federation_entry_invalid"))
            continue
        identity = f"{source_key}\n{resource_type}\n{resource_id}"
        if identity in seen or _same_provenance(provenance, resource_type, resource):
            continue
        seen.add(identity)
        meta_source = _meta_source(resource)
        full_url = entry.get("fullUrl") if isinstance(entry.get("fullUrl"), str) else ""
        reference = _reference(resource_type, resource_id, source_key, references)
        references.add(reference)
        if resource_type in _TIMELINE_TYPES:
            if meta_source is None:
                gaps.append(LongitudinalGap(code="provenance_missing", reference=reference))
            facts.append(
                LongitudinalFact(
                    reference=reference,
                    status=resource.get("status") if isinstance(resource.get("status"), str) else None,
                    instant=_instant(resource, resource_type),
                    end=_text(_nested(resource, "period", "end")) if resource_type == "Encounter" else None,
                    related=_related(resource),
                    source=meta_source,
                    recordedValue=_recorded_value(resource) if resource_type == "Observation" else None,
                )
            )
            rows.append(_row(reference, resource_type, source_key, full_url, meta_source, resource, fact=facts[-1]))
        elif resource_type in _REPORT_TYPES:
            reports.append(_row(reference, resource_type, source_key, full_url, meta_source, resource))
        elif resource_type == "Patient":
            rows.append(_row(reference, resource_type, source_key, full_url, meta_source, resource))
        if resource_type in _TIMELINE_TYPES or resource_type == "Patient":
            _remember_provenance(provenance, resource_type, resource)
    return facts, reports, gaps, rows


def _reference(resource_type: str, resource_id: str, source_key: str, used: set[str]) -> str:
    plain = f"{resource_type}/{resource_id}"
    if plain not in used:
        return plain
    return f"{resource_type}/{source_key}~{resource_id}"


def _same_provenance(seen: set[str], resource_type: str, resource: dict) -> bool:
    meta_source = _meta_source(resource)
    if not meta_source:
        return False
    for system, value in _identifiers(resource):
        key = f"{resource_type}\n{meta_source}\n{system}\n{value}"
        if key in seen:
            return True
    return False


def _remember_provenance(seen: set[str], resource_type: str, resource: dict) -> None:
    meta_source = _meta_source(resource)
    if not meta_source:
        return
    for system, value in _identifiers(resource):
        seen.add(f"{resource_type}\n{meta_source}\n{system}\n{value}")


def _row(
    reference: str,
    resource_type: str,
    source_key: str,
    full_url: str,
    meta_source: str | None,
    resource: dict,
    fact: LongitudinalFact | None = None,
) -> dict:
    return {
        "reference": reference,
        "resourceType": resource_type,
        "status": resource.get("status") if isinstance(resource.get("status"), str) else None,
        "instant": None if fact is None else fact.instant,
        "sourceKey": source_key,
        "source": meta_source,
        "fullUrl": full_url,
        "identifiers": [{"system": system, "value": value} for system, value in _identifiers(resource)],
        "related": [] if fact is None else list(fact.related),
        "code": _code(resource),
        "value": _quantity(resource)[0],
        "unit": _quantity(resource)[1],
        "protocolReference": f"{resource_type}/{resource.get('id')}",
    }


def _projection(
    context: LongitudinalContext,
    envelope: dict,
    sources: list[dict],
    warnings: list[str],
    rows: list[dict],
    reports: list[dict],
) -> dict:
    return {
        "status": envelope.get("status"),
        "correlationId": envelope.get("correlationId"),
        "sources": sources,
        "warnings": warnings,
        "resources": rows,
        "reports": reports,
        "contextStatus": context.status,
        "callerSystem": envelope.get("callerSystem") if isinstance(envelope.get("callerSystem"), str) else None,
    }


def _sources(envelope: dict) -> list[dict]:
    sources: list[dict] = []
    for item in envelope.get("sources") or []:
        if not isinstance(item, dict) or not isinstance(item.get("sourceKey"), str):
            continue
        sources.append(
            {
                "sourceKey": item.get("sourceKey"),
                "organizationId": item.get("organizationId") if isinstance(item.get("organizationId"), str) else "",
                "outcome": item.get("outcome") if isinstance(item.get("outcome"), str) else "",
                "resourceCount": item.get("resourceCount") if isinstance(item.get("resourceCount"), int) else 0,
                "error": item.get("error") if isinstance(item.get("error"), str) else None,
            }
        )
    return sources


def _warnings(status: object, sources: list[dict]) -> list[str]:
    warnings: list[str] = []
    if status == "failed":
        warnings.append("federation_failed")
    elif status == "partial":
        warnings.append("federation_partial")
    for source in sources:
        outcome = source["outcome"]
        if outcome in _FAILURE_OUTCOMES:
            warnings.append(f"{outcome}:{source['sourceKey']}")
        elif outcome == "complete" and source["resourceCount"] == 0:
            warnings.append(f"no_resources:{source['sourceKey']}")
    return warnings


def _caller_patient_id(envelope: dict, facts: list[LongitudinalFact]) -> str | None:
    caller = envelope.get("callerSystem")
    for entry in envelope.get("entries") or []:
        if not isinstance(entry, dict):
            continue
        resource = entry.get("resource")
        if not isinstance(resource, dict) or resource.get("resourceType") != "Patient":
            continue
        if caller and entry.get("sourceKey") != caller:
            continue
        patient_id = resource.get("id")
        if isinstance(patient_id, str) and validated_fhir_id(patient_id):
            return patient_id
    del facts
    return None


def _meta_source(resource: dict) -> str | None:
    meta = resource.get("meta")
    source = meta.get("source") if isinstance(meta, dict) else None
    return source if isinstance(source, str) and source.strip() else None


def _code(resource: dict) -> dict | None:
    code = resource.get("code")
    if not isinstance(code, dict):
        return None
    coding = code.get("coding")
    if not isinstance(coding, list) or not coding or not isinstance(coding[0], dict):
        return None
    system = coding[0].get("system")
    value = coding[0].get("code")
    if isinstance(system, str) and system and isinstance(value, str) and value:
        return {"system": system, "code": value}
    return None


def _quantity(resource: dict) -> tuple[str | None, str | None]:
    quantity = resource.get("valueQuantity")
    if isinstance(quantity, dict) and quantity.get("value") is not None and not isinstance(quantity.get("value"), bool):
        unit = quantity.get("unit")
        return str(quantity.get("value")), unit if isinstance(unit, str) and unit else None
    text = resource.get("valueString")
    if isinstance(text, str) and text.strip():
        return text.strip()[:80], None
    return None, None


def _identifiers(resource: dict) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    identifiers = resource.get("identifier")
    if not isinstance(identifiers, list):
        return found
    for item in identifiers:
        if not isinstance(item, dict):
            continue
        system = item.get("system")
        value = item.get("value")
        if isinstance(system, str) and system and isinstance(value, str) and value:
            found.append((system, value))
    return found


def _instant(resource: dict, resource_type: str) -> str | None:
    if resource_type == "Encounter":
        return _text(_nested(resource, "period", "start"))
    if resource_type == "Observation":
        return _text(resource.get("issued")) or _text(resource.get("effectiveDateTime"))
    return _text(resource.get("start"))


def _related(resource: dict) -> list[str]:
    related: list[str] = []
    for field in ("subject", "encounter", "basedOn"):
        value = resource.get(field)
        nodes = value if isinstance(value, list) else [value]
        for node in nodes:
            reference = node.get("reference") if isinstance(node, dict) else None
            if isinstance(reference, str) and reference:
                related.append(reference)
    return related


def _recorded_value(resource: dict) -> str | None:
    quantity = resource.get("valueQuantity")
    if isinstance(quantity, dict) and quantity.get("value") is not None:
        value = quantity.get("value")
        if isinstance(value, bool) or not isinstance(value, (int, float, str)):
            return None
        text = str(value).strip()
        unit = quantity.get("unit")
        if isinstance(unit, str) and unit.strip():
            text = f"{text} {unit.strip()}"
        return text[:80] or None
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
