"""Run the existing follow-up rules on a federation envelope.

The workflow type selects the protocol. Laboratory values do not. A fullUrl is a
locator inside the envelope, not a FHIR server to call.
"""

from __future__ import annotations

import re
from copy import deepcopy
from datetime import datetime

from app.langgraph_fhir_followup import appointment_classification
from app.missed_follow_up_review import (
    MISSED_FOLLOW_UP_REVIEW_V1,
    MissedFollowUpAppointment,
    MissedFollowUpSnapshot,
    evaluate_missed_follow_up,
)
from app.post_consultation_review import (
    POST_CONSULTATION_RESULT_REVIEW_V1,
    AppointmentFact,
    CollectionState,
    PostConsultationSnapshot,
    ProtocolEvaluationStatus,
    ProtocolReviewResult,
    evaluate_post_consultation_review,
    parse_fhir_reference,
)


POST_CONSULTATION = "post_consultation"
MISSED_FOLLOW_UP = "missed_follow_up"
_TAIL = re.compile(
    r"(Patient|Encounter|Observation|Appointment|ServiceRequest|DiagnosticReport)/([A-Za-z0-9.-]{1,64})$"
)
_FAILURES = frozenset({
    "identity_unresolved",
    "unavailable",
    "connector_unavailable",
    "not_registered",
    "capability_unsupported",
    "limit_reached",
})


def evaluate_federated_protocol(
    envelope: dict,
    workflow_type: str,
    evaluated_at: datetime,
) -> tuple[dict, ProtocolReviewResult | None]:
    """Return the graph protocol view and, only for a match, the review trigger."""
    if envelope.get("status") not in {"complete", "partial"}:
        return _view(workflow_type, "unavailable", ("federation_failed",), ()), None
    if envelope.get("status") != "complete" or envelope.get("truncated"):
        reasons = ["federated_context_partial"]
        reasons.extend(_failure_reasons(envelope))
        return _view(workflow_type, "insufficient", tuple(reasons), ()), None
    if workflow_type == MISSED_FOLLOW_UP:
        return _missed(envelope, evaluated_at)
    if workflow_type == POST_CONSULTATION:
        return _post_consultation(envelope, evaluated_at)
    return _view(workflow_type, "unavailable", ("evaluation_unavailable",), ()), None


def federated_narrative(state: dict) -> str:
    """Quote the rule result and the read evidence. Do not add a clinical conclusion."""
    protocol = state.get("protocol_result") if isinstance(state.get("protocol_result"), dict) else {}
    context = state.get("clinical_context") if isinstance(state.get("clinical_context"), dict) else {}
    federation = context.get("federation") if isinstance(context.get("federation"), dict) else {}
    resources = federation.get("resources") if isinstance(federation.get("resources"), list) else []
    evidence = [item for item in state.get("evidence") or [] if isinstance(item, str)]
    lines = [
        "Propuesta sintética de laboratorio.",
        "La regla determinista produjo este resultado. Un modelo no lo cambió.",
        f"Protocolo: {protocol.get('protocolId') or 'sin protocolo'}.",
        f"Resultado: {protocol.get('evaluationStatus') or 'sin estado'}.",
        "Motivos: " + ", ".join(str(item) for item in protocol.get("reasonCodes") or []) + ".",
        "Evidencia usada por la regla:",
    ]
    caller = federation.get("callerSystem") if isinstance(federation.get("callerSystem"), str) else ""
    lines.extend(_resource_line(item, resources, caller) for item in evidence)
    lines.append("Otra evidencia leída, con su origen:")
    others = [
        item
        for item in resources
        if isinstance(item, dict) and not _cited(item, evidence, caller)
    ]
    if others:
        lines.extend(_described(item) for item in others[:8])
    else:
        lines.append("Ninguna.")
    warnings = federation.get("warnings") if isinstance(federation.get("warnings"), list) else []
    if warnings:
        lines.append("Advertencias: " + ", ".join(str(item) for item in warnings) + ".")
    lines.append("Esta propuesta no es una decisión clínica. La revisión humana sigue siendo obligatoria.")
    return "\n".join(lines)


def _post_consultation(envelope: dict, evaluated_at: datetime) -> tuple[dict, ProtocolReviewResult | None]:
    patient_id = _caller_patient_id(envelope)
    resources = _caller_resources(envelope)
    appointments = tuple(
        AppointmentFact(
            reference=f"Appointment/{item.get('id')}",
            classification=appointment_classification(item.get("status"), item.get("start"), evaluated_at),
        )
        for item in resources
        if item.get("resourceType") == "Appointment"
    )
    snapshot = PostConsultationSnapshot(
        patient_id=patient_id,
        patient_state=CollectionState.COMPLETE,
        encounter_state=CollectionState.COMPLETE,
        observation_state=CollectionState.COMPLETE,
        appointment_state=CollectionState.COMPLETE,
        encounters=tuple(item for item in resources if item.get("resourceType") == "Encounter"),
        observations=tuple(item for item in resources if item.get("resourceType") == "Observation"),
        appointments=appointments,
    )
    result = evaluate_post_consultation_review(snapshot)
    review = result if result.evaluation_status is ProtocolEvaluationStatus.MATCHED else None
    return _from_result(result.id, result.evaluation_status.value, result.reason_codes, result.matched_resources), review


def _missed(envelope: dict, evaluated_at: datetime) -> tuple[dict, ProtocolReviewResult | None]:
    patient_id = _caller_patient_id(envelope)
    appointments = []
    for resource in _caller_resources(envelope):
        if resource.get("resourceType") != "Appointment" or not isinstance(resource.get("id"), str):
            continue
        start = _parsed_start(resource.get("start"))
        appointments.append(
            MissedFollowUpAppointment(
                reference=f"Appointment/{resource['id']}",
                appointment_id=resource["id"],
                status=resource.get("status") if isinstance(resource.get("status"), str) else "",
                start=start,
            )
        )
    snapshot = MissedFollowUpSnapshot(
        patient_id=patient_id,
        patient_state=CollectionState.COMPLETE,
        appointment_state=CollectionState.COMPLETE,
        appointments=tuple(appointments),
        evaluated_at=evaluated_at,
    )
    result = evaluate_missed_follow_up(snapshot)
    review = None
    evidence = result.triggers or result.provenance_resources
    if result.status is ProtocolEvaluationStatus.MATCHED and result.triggers:
        review = ProtocolReviewResult(
            id=MISSED_FOLLOW_UP_REVIEW_V1,
            evaluation_status=result.status,
            reason_codes=result.reason_codes,
            matched_resources=(result.triggers[0],),
            human_review_status="required",
            human_review_reason="deterministic_missed_follow_up_protocol_match",
            action_status="proposed",
            action_type="review_follow_up_case",
        )
        evidence = (result.triggers[0],)
    return _from_result(MISSED_FOLLOW_UP_REVIEW_V1, result.status.value, result.reason_codes, evidence), review


def _caller_resources(envelope: dict) -> list[dict]:
    """Rule inputs stay inside the caller source. Another source keeps its own ids."""
    caller = envelope.get("callerSystem")
    if not isinstance(caller, str) or not caller:
        return []
    resources: list[dict] = []
    for entry in envelope.get("entries") or []:
        if not isinstance(entry, dict) or entry.get("sourceKey") != caller:
            continue
        resource = entry.get("resource")
        if not isinstance(resource, dict):
            continue
        full_url = entry.get("fullUrl") if isinstance(entry.get("fullUrl"), str) else ""
        resources.append(_relative_resource(resource, _source_base(full_url)))
    return resources


def _relative_resource(resource: dict, source_base: str | None) -> dict:
    copied = deepcopy(resource)
    for field in ("subject", "encounter"):
        node = copied.get(field)
        if isinstance(node, dict) and isinstance(node.get("reference"), str):
            relative = _relative(node["reference"], source_base)
            if relative is not None:
                node["reference"] = relative
    return copied


def _source_base(full_url: str) -> str | None:
    match = _TAIL.search(full_url)
    if match is None:
        return None
    base = full_url[: match.start()].rstrip("/")
    return base or None


def _relative(reference: str, source_base: str | None) -> str | None:
    if parse_fhir_reference(reference, reference.split("/", 1)[0]) is not None and reference.count("/") == 1:
        return reference
    match = _TAIL.search(reference)
    if match is None or not source_base:
        return None
    base = reference[: match.start()].rstrip("/")
    if base != source_base:
        return None
    return f"{match.group(1)}/{match.group(2)}"


def _caller_patient_id(envelope: dict) -> str | None:
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
        if isinstance(patient_id, str) and patient_id:
            return patient_id
    return None


def _failure_reasons(envelope: dict) -> list[str]:
    found: list[str] = []
    for item in envelope.get("sources") or []:
        if isinstance(item, dict) and item.get("outcome") in _FAILURES and item["outcome"] not in found:
            found.append(item["outcome"])
    return found


def _parsed_start(raw: object) -> datetime | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        parsed = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed


def _view(workflow_type: str, status: str, reasons: tuple[str, ...], evidence: tuple[str, ...]) -> dict:
    protocol_id = {
        POST_CONSULTATION: POST_CONSULTATION_RESULT_REVIEW_V1,
        MISSED_FOLLOW_UP: MISSED_FOLLOW_UP_REVIEW_V1,
    }.get(workflow_type, workflow_type)
    return _from_result(protocol_id, status, reasons, evidence)


def _from_result(protocol_id: str, status: str, reasons: tuple[str, ...], evidence: tuple[str, ...]) -> dict:
    return {
        "protocolId": protocol_id,
        "evaluationStatus": status,
        "reasonCodes": list(reasons)[:8],
        "evidence": list(evidence)[:8],
    }


def _cited(item: dict, evidence: list[str], caller: str) -> bool:
    reference = item.get("protocolReference") or item.get("reference")
    display = item.get("reference")
    if reference not in evidence and display not in evidence:
        return False
    source = item.get("sourceKey")
    return not caller or source == caller


def _resource_line(reference: str, resources: list, caller: str) -> str:
    matches = [
        item
        for item in resources
        if isinstance(item, dict) and (item.get("protocolReference") == reference or item.get("reference") == reference)
    ]
    owned = [item for item in matches if not caller or item.get("sourceKey") == caller]
    chosen = owned[0] if owned else (matches[0] if matches else None)
    if chosen is None:
        return reference
    return _described(chosen)


def _described(item: dict) -> str:
    value = item.get("value") or ""
    unit = item.get("unit") or ""
    shown = f"{value} {unit}".strip()
    code = item.get("code") if isinstance(item.get("code"), dict) else {}
    return (
        f"{item.get('protocolReference') or item.get('reference')} "
        f"origen={item.get('sourceKey') or 'sin origen'} "
        f"sistema={item.get('source') or 'sin sistema'} "
        f"estado={item.get('status') or 'sin estado'} "
        f"fecha={item.get('instant') or 'sin fecha'} "
        f"codigo={code.get('code') or 'sin codigo'} "
        f"valor={shown or 'sin valor'}"
    )
