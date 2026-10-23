"""Structural cross-organization laboratory review.

The workflow type selects this protocol. Laboratory values do not. A resource
from one source is not the same resource because its local id matches another.
"""

from __future__ import annotations

import re
from copy import deepcopy

from app.post_consultation_review import (
    ProtocolEvaluationStatus,
    ProtocolReviewResult,
    parse_fhir_reference,
)


CROSS_ORG_LAB_RESULT_REVIEW_V1 = "CROSS_ORG_LAB_RESULT_REVIEW_V1"
CROSS_ORG_LAB_RESULT = "cross_org_lab_result"
HIS_ORDER_SYSTEM = "https://lab.local/mini-his/order"
LIS_ORDER_SYSTEM = "https://lab.local/mini-lis/order"
REASON_MATCHED = "cross_org_lab_result_requires_review"
_TAIL = re.compile(
    r"(Patient|Encounter|Observation|ServiceRequest|DiagnosticReport)/([A-Za-z0-9.-]{1,64})$"
)


def evaluate_cross_org_lab_result(envelope: dict) -> tuple[dict, ProtocolReviewResult | None]:
    """Require a finished HIS encounter, a submitted HIS order, and the linked LIS result."""
    caller = envelope.get("callerSystem")
    his_patient = _caller_patient(envelope, caller)
    if his_patient is None:
        return _view("insufficient", ("authorized_patient_missing",), ()), None
    patient_id, organization_id = his_patient
    if envelope.get("requestingOrganizationId") != organization_id:
        return _view("insufficient", ("organization_correlation_missing",), ()), None
    entries = _entries(envelope)
    encounters = [
        item
        for item in entries
        if item["sourceKey"] == caller
        and item["type"] == "Encounter"
        and item["resource"].get("status") == "finished"
        and _subject_id(item) == patient_id
    ]
    if not encounters:
        return _view("insufficient", ("finished_encounter_missing",), ()), None
    encounter = sorted(encounters, key=lambda item: item["id"])[0]
    orders = [
        item
        for item in entries
        if item["sourceKey"] == caller
        and item["type"] == "ServiceRequest"
        and _subject_id(item) == patient_id
        and _identifier(item["resource"], HIS_ORDER_SYSTEM) == item["id"]
    ]
    active = [item for item in orders if item["resource"].get("status") == "active"]
    if not active:
        if any(item["resource"].get("status") == "draft" for item in orders):
            return _view("not_matched", ("order_not_submitted",), ()), None
        return _view("insufficient", ("his_order_missing",), ()), None
    lis_patients = {
        item["id"]
        for item in entries
        if item["sourceKey"] != caller
        and item["type"] == "Patient"
        and _identifier(item["resource"], _external_patient_system(organization_id)) == patient_id
    }
    if not lis_patients:
        return _view("insufficient", ("patient_correlation_missing",), ()), None
    linked: list[tuple[dict, dict]] = []
    ambiguous = False
    for order in sorted(active, key=lambda item: item["id"]):
        matches = [
            request
            for request in entries
            if request["sourceKey"] != caller
            and request["type"] == "ServiceRequest"
            and _identifier(request["resource"], LIS_ORDER_SYSTEM) == order["id"]
            and _requester_value(request["resource"]) == organization_id
            and _subject_id(request) in lis_patients
        ]
        if len(matches) > 1:
            ambiguous = True
            continue
        if len(matches) == 1:
            linked.append((order, matches[0]))
    if not linked:
        reason = "order_correlation_ambiguous" if ambiguous else "order_correlation_missing"
        return _view("insufficient", (reason,), ()), None
    saw_preliminary = False
    linked_ids = {request["id"] for _order, request in linked}
    for order, request in linked:
        observations = _observations_for(entries, request, lis_patients)
        finals = [item for item in observations if item["resource"].get("status") == "final"]
        if finals:
            observation = sorted(finals, key=lambda item: item["id"])[0]
            evidence = (
                f"Encounter/{encounter['id']}",
                f"ServiceRequest/{order['id']}",
                f"ServiceRequest/{request['id']}",
                f"Observation/{observation['id']}",
            )
            review = ProtocolReviewResult(
                id=CROSS_ORG_LAB_RESULT_REVIEW_V1,
                evaluation_status=ProtocolEvaluationStatus.MATCHED,
                reason_codes=(REASON_MATCHED,),
                matched_resources=evidence,
                human_review_status="required",
                human_review_reason="deterministic_cross_org_lab_result_protocol_match",
                action_status="proposed",
                action_type="review_follow_up_case",
            )
            return _view("matched", (REASON_MATCHED,), evidence), review
        if any(item["resource"].get("status") == "preliminary" for item in observations):
            saw_preliminary = True
    other_final = any(
        item["type"] == "Observation"
        and item["sourceKey"] != caller
        and item["resource"].get("status") == "final"
        and not set(_based_on_ids(item)).intersection(linked_ids)
        for item in entries
    )
    if other_final:
        return _view("not_matched", ("result_order_mismatch",), ()), None
    if saw_preliminary:
        return _view("not_matched", ("result_not_final",), ()), None
    return _view("insufficient", ("final_result_missing",), ()), None


def _caller_patient(envelope: dict, caller: object) -> tuple[str, str] | None:
    if not isinstance(caller, str) or not caller:
        return None
    for entry in envelope.get("entries") or []:
        if not isinstance(entry, dict) or entry.get("sourceKey") != caller:
            continue
        resource = entry.get("resource")
        if not isinstance(resource, dict) or resource.get("resourceType") != "Patient":
            continue
        patient_id = resource.get("id")
        organization_id = entry.get("organizationId")
        if isinstance(patient_id, str) and patient_id and isinstance(organization_id, str) and organization_id:
            return patient_id, organization_id
    return None


def _entries(envelope: dict) -> list[dict]:
    found: list[dict] = []
    for entry in envelope.get("entries") or []:
        if not isinstance(entry, dict) or not isinstance(entry.get("resource"), dict):
            continue
        source = entry.get("sourceKey")
        resource = entry["resource"]
        resource_id = resource.get("id")
        resource_type = resource.get("resourceType")
        if not isinstance(source, str) or not isinstance(resource_id, str) or not isinstance(resource_type, str):
            continue
        full_url = entry.get("fullUrl") if isinstance(entry.get("fullUrl"), str) else ""
        found.append(
            {
                "sourceKey": source,
                "id": resource_id,
                "type": resource_type,
                "base": _source_base(full_url),
                "resource": _relative_resource(resource, _source_base(full_url)),
            }
        )
    return found


def _observations_for(entries: list[dict], request: dict, patients: set[str]) -> list[dict]:
    return [
        item
        for item in entries
        if item["sourceKey"] == request["sourceKey"]
        and item["type"] == "Observation"
        and request["id"] in _based_on_ids(item)
        and _subject_id(item) in patients
    ]


def _based_on_ids(item: dict) -> list[str]:
    nodes = item["resource"].get("basedOn")
    nodes = nodes if isinstance(nodes, list) else [nodes]
    found: list[str] = []
    for node in nodes:
        reference = node.get("reference") if isinstance(node, dict) else None
        relative = _relative(reference, item["base"]) if isinstance(reference, str) else None
        if relative is not None and relative.startswith("ServiceRequest/"):
            found.append(relative.split("/", 1)[1])
    return found


def _subject_id(item: dict) -> str | None:
    subject = item["resource"].get("subject")
    reference = subject.get("reference") if isinstance(subject, dict) else None
    relative = _relative(reference, item["base"]) if isinstance(reference, str) else None
    if relative is not None and relative.startswith("Patient/"):
        return relative.split("/", 1)[1]
    return None


def _requester_value(resource: dict) -> str | None:
    requester = resource.get("requester")
    identifier = requester.get("identifier") if isinstance(requester, dict) else None
    value = identifier.get("value") if isinstance(identifier, dict) else None
    return value if isinstance(value, str) and value else None


def _identifier(resource: dict, system: str) -> str | None:
    for item in resource.get("identifier") or []:
        if isinstance(item, dict) and item.get("system") == system and isinstance(item.get("value"), str):
            return item["value"]
    return None


def _external_patient_system(organization_id: str) -> str:
    return f"https://lab.local/mini-lis/organization/{organization_id}/patient"


def _relative_resource(resource: dict, source_base: str | None) -> dict:
    copied = deepcopy(resource)
    for field in ("subject", "encounter"):
        node = copied.get(field)
        if isinstance(node, dict) and isinstance(node.get("reference"), str):
            relative = _relative(node["reference"], source_base)
            if relative is not None:
                node["reference"] = relative
    based_on = copied.get("basedOn")
    nodes = based_on if isinstance(based_on, list) else []
    for node in nodes:
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
    if reference[: match.start()].rstrip("/") != source_base:
        return None
    return f"{match.group(1)}/{match.group(2)}"


def _view(status: str, reasons: tuple[str, ...], evidence: tuple[str, ...]) -> dict:
    return {
        "protocolId": CROSS_ORG_LAB_RESULT_REVIEW_V1,
        "evaluationStatus": status,
        "reasonCodes": list(reasons),
        "evidence": list(evidence),
    }
