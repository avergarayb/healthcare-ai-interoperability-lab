"""Minimize a Clinical Federation envelope. Names and dates of birth stay out of the model."""
import json
import re

from app.enterprise_llm_providers.errors import ProviderError

from .policy import OPERATION_ID, RESOURCE_TYPES, SOURCES


_PATIENT = re.compile(r"MHS-PAT-[0-9]{3}\Z")
_FACT_ID = re.compile(r"[A-Za-z0-9.-]{1,64}\Z")
_NUMBER = re.compile(r"[0-9]+(?:\.[0-9]+)?\Z")
_DROPPED = frozenset({"name", "birthDate", "address", "telecom", "family", "given", "photo"})


def minimize_envelope(envelope, patient_id):
    """Keep final lab facts from both sources. A partial chart is not a summary."""
    if not isinstance(envelope, dict) or envelope.get("contractVersion") != "clinical-federation-v1":
        raise ProviderError("context_rejected")
    if envelope.get("status") != "complete" or envelope.get("truncated") is not False:
        raise ProviderError("context_incomplete")
    if not _PATIENT.fullmatch(patient_id or ""):
        raise ProviderError("context_rejected")
    sources = envelope.get("sources")
    entries = envelope.get("entries")
    if not isinstance(sources, list) or not isinstance(entries, list):
        raise ProviderError("context_rejected")
    outcomes = {}
    for item in sources:
        if not isinstance(item, dict) or item.get("sourceKey") not in SOURCES:
            raise ProviderError("context_rejected")
        outcomes[item["sourceKey"]] = item.get("outcome")
    if outcomes.get("mini-his") != "complete" or outcomes.get("mini-lis") != "complete":
        raise ProviderError("context_incomplete")
    facts = []
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("sourceKey") not in SOURCES:
            raise ProviderError("context_rejected")
        resource = entry.get("resource")
        if not isinstance(resource, dict):
            raise ProviderError("context_rejected")
        if resource.get("resourceType") == "Patient":
            continue
        if resource.get("resourceType") not in RESOURCE_TYPES:
            continue
        fact = _fact(entry["sourceKey"], resource)
        if fact is not None:
            facts.append(fact)
    if not any(item["source"] == "mini-his" and item["resourceType"] == "Observation" for item in facts):
        raise ProviderError("context_incomplete")
    if not any(item["source"] == "mini-lis" and item["resourceType"] == "Observation" for item in facts):
        raise ProviderError("context_incomplete")
    chart = {"operation_id": OPERATION_ID, "patient_id": patient_id, "facts": facts}
    require_model_context(chart, patient_id)
    return chart


def require_model_context(chart, resource_id):
    """Reject a chart that carries identity fields or a patient other than the permit."""
    if not isinstance(chart, dict) or set(chart) != {"operation_id", "patient_id", "facts"}:
        raise ProviderError("context_rejected")
    if chart["operation_id"] != OPERATION_ID or chart["patient_id"] != resource_id:
        raise ProviderError("context_rejected")
    if not _PATIENT.fullmatch(chart["patient_id"]):
        raise ProviderError("context_rejected")
    facts = chart["facts"]
    if not isinstance(facts, list) or not facts or len(facts) > 8:
        raise ProviderError("context_rejected")
    seen = set()
    for fact in facts:
        if not isinstance(fact, dict) or set(fact) != {
                "source", "resourceType", "id", "status", "code", "value", "unit"}:
            raise ProviderError("context_rejected")
        if fact["source"] not in SOURCES or fact["resourceType"] not in RESOURCE_TYPES:
            raise ProviderError("context_rejected")
        if fact["status"] != "final" or not _FACT_ID.fullmatch(fact["id"]):
            raise ProviderError("context_rejected")
        if not _FACT_ID.fullmatch(fact["code"]) or len(fact["value"]) > 32 or len(fact["unit"]) > 16:
            raise ProviderError("context_rejected")
        if fact["resourceType"] == "Observation" and _NUMBER.fullmatch(fact["value"]) is None:
            raise ProviderError("context_rejected")
        key = (fact["source"], fact["resourceType"], fact["id"])
        if key in seen:
            raise ProviderError("context_rejected")
        seen.add(key)
    rendered = json.dumps(chart, ensure_ascii=True)
    if any(name in rendered for name in _DROPPED) or "AIza" in rendered or "GEMINI_API_KEY" in rendered:
        raise ProviderError("context_rejected")
    return chart


def _fact(source, resource):
    """Keep one final numeric lab fact. A panel or a non-numeric sign is omitted."""
    code = _code(resource)
    quantity = resource.get("valueQuantity") if isinstance(resource.get("valueQuantity"), dict) else {}
    value = quantity.get("value")
    unit = quantity.get("unit") if isinstance(quantity.get("unit"), str) else ""
    if resource.get("resourceType") == "DiagnosticReport":
        if resource.get("status") != "final" or not code:
            return None
        value, unit = code, ""
    elif type(value) is float or type(value) is int:
        value = format(value, "g")
    else:
        return None
    if resource.get("status") != "final" or _FACT_ID.fullmatch(code or "") is None:
        return None
    if _FACT_ID.fullmatch(str(resource.get("id") or "")) is None:
        return None
    return {
        "source": source,
        "resourceType": resource.get("resourceType"),
        "id": resource.get("id"),
        "status": "final",
        "code": code,
        "value": value,
        "unit": unit,
    }


def _code(resource):
    coding = resource.get("code") if isinstance(resource.get("code"), dict) else {}
    codes = coding.get("coding") if isinstance(coding.get("coding"), list) else []
    if codes and isinstance(codes[0], dict) and isinstance(codes[0].get("code"), str) and codes[0]["code"]:
        return codes[0]["code"]
    text = coding.get("text")
    return text if isinstance(text, str) else ""
