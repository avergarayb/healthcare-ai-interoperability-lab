"""Minimize one external federation envelope. Unverified quantities are not model facts."""
import json
import re

from app.enterprise_llm_providers.errors import ProviderError

from .policy import OPERATION_ID, PATIENT_ID, SOURCE


_FACT_ID = re.compile(r"[A-Za-z0-9.-]{1,64}\Z")
_NUMBER = re.compile(r"[0-9]+(?:\.[0-9]+)?\Z")
_DROPPED = frozenset({"name", "birthDate", "address", "telecom", "family", "given", "photo"})
_UCUM = "http://unitsofmeasure.org"
_TAG = "https://lab.local/external-fhir/verification"


def minimize_envelope(envelope, patient_id):
    """Keep at most eight verified final observations from the external source."""
    if not isinstance(envelope, dict) or envelope.get("contractVersion") != "clinical-federation-v1":
        raise ProviderError("context_rejected")
    if envelope.get("status") != "complete" or envelope.get("truncated") is not False:
        raise ProviderError("context_incomplete")
    if patient_id != PATIENT_ID:
        raise ProviderError("context_rejected")
    sources = envelope.get("sources")
    entries = envelope.get("entries")
    if not isinstance(sources, list) or len(sources) != 1 or not isinstance(entries, list):
        raise ProviderError("context_rejected")
    source = sources[0]
    if not isinstance(source, dict) or source.get("sourceKey") != SOURCE or source.get("outcome") != "complete":
        raise ProviderError("context_rejected")
    _one_patient(entries)
    facts = []
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("sourceKey") != SOURCE:
            raise ProviderError("context_rejected")
        fact = _fact(entry.get("resource"))
        if fact is not None and len(facts) < 8:
            facts.append(fact)
    if not facts:
        raise ProviderError("context_incomplete")
    chart = {"operation_id": OPERATION_ID, "patient_id": patient_id, "facts": facts}
    return require_model_context(chart, patient_id)


def require_model_context(chart, resource_id):
    if not isinstance(chart, dict) or set(chart) != {"operation_id", "patient_id", "facts"}:
        raise ProviderError("context_rejected")
    if chart["operation_id"] != OPERATION_ID or chart["patient_id"] != resource_id:
        raise ProviderError("context_rejected")
    facts = chart["facts"]
    if not isinstance(facts, list) or not facts or len(facts) > 8:
        raise ProviderError("context_rejected")
    seen = set()
    for fact in facts:
        if not isinstance(fact, dict) or set(fact) != {
                "source", "resourceType", "id", "status", "code", "value", "unit"}:
            raise ProviderError("context_rejected")
        if fact["source"] != SOURCE or fact["resourceType"] != "Observation" or fact["status"] != "final":
            raise ProviderError("context_rejected")
        if _FACT_ID.fullmatch(fact["id"]) is None or _FACT_ID.fullmatch(fact["code"]) is None:
            raise ProviderError("context_rejected")
        if _NUMBER.fullmatch(fact["value"]) is None or len(fact["unit"]) > 32:
            raise ProviderError("context_rejected")
        key = (fact["source"], fact["id"])
        if key in seen:
            raise ProviderError("context_rejected")
        seen.add(key)
    rendered = json.dumps(chart, ensure_ascii=True)
    if any(name in rendered for name in _DROPPED):
        raise ProviderError("context_rejected")
    return chart


def validate_summary(chart, parsed):
    """Accept one intercepted summary only when every citation is a chart fact."""
    if not isinstance(parsed, dict) or set(parsed) != {"kind", "statements", "review"}:
        raise ProviderError("invalid_output")
    if parsed["kind"] != OPERATION_ID or parsed["review"] != "pending_human_review":
        raise ProviderError("invalid_output")
    statements = parsed["statements"]
    if not isinstance(statements, list) or not statements or len(statements) > 8:
        raise ProviderError("invalid_output")
    known = {(item["source"], item["resourceType"], item["id"]): item for item in chart["facts"]}
    checked = []
    for item in statements:
        if not isinstance(item, dict) or set(item) != {"text", "sources"}:
            raise ProviderError("invalid_output")
        text = item["text"]
        if type(text) is not str or text.strip() == "" or len(text) > 400:
            raise ProviderError("invalid_output")
        sources = item["sources"]
        if not isinstance(sources, list) or not sources or len(sources) > 4:
            raise ProviderError("invalid_output")
        cited = []
        for source in sources:
            if not isinstance(source, dict) or set(source) != {"source", "resourceType", "id"}:
                raise ProviderError("invalid_output")
            key = (source["source"], source["resourceType"], source["id"])
            fact = known.get(key)
            if fact is None or fact["value"] not in text:
                raise ProviderError("invalid_output")
            cited.append({"source": key[0], "resourceType": key[1], "id": key[2]})
        checked.append({"text": text, "sources": cited})
    return {"kind": OPERATION_ID, "review": "pending_human_review", "statements": checked}


def _one_patient(entries):
    """A second patient reference denies the chart. A missing subject is not a link."""
    found = []
    for entry in entries:
        resource = entry.get("resource") if isinstance(entry, dict) else None
        if not isinstance(resource, dict) or resource.get("resourceType") != "Observation":
            continue
        subject = resource.get("subject")
        if subject is None:
            continue
        if not isinstance(subject, dict):
            raise ProviderError("context_rejected")
        found.append(_logical_patient(subject.get("reference")))
    if len(set(found)) > 1:
        raise ProviderError("context_rejected")


def _logical_patient(reference):
    prefix = "https://r4.smarthealthit.org/Patient/"
    if type(reference) is not str:
        raise ProviderError("context_rejected")
    if reference.startswith(prefix):
        logical = reference[len(prefix):]
    elif reference.startswith("Patient/"):
        logical = reference[len("Patient/"):]
    else:
        raise ProviderError("context_rejected")
    if _FACT_ID.fullmatch(logical) is None:
        raise ProviderError("context_rejected")
    return logical


def _fact(resource):
    if not isinstance(resource, dict) or resource.get("resourceType") != "Observation":
        return None
    if resource.get("status") != "final" or not _tagged(resource, "quantity-verified"):
        return None
    quantity = resource.get("valueQuantity")
    if not isinstance(quantity, dict) or quantity.get("system") != _UCUM:
        return None
    code = quantity.get("code")
    unit = quantity.get("unit") or code
    value = quantity.get("value")
    observation_code = _code(resource)
    if type(code) is not str or unit != code or not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    rendered = format(value, "g")
    if _NUMBER.fullmatch(rendered) is None or _FACT_ID.fullmatch(observation_code or "") is None:
        return None
    if _FACT_ID.fullmatch(str(resource.get("id") or "")) is None:
        return None
    return {
        "source": SOURCE,
        "resourceType": "Observation",
        "id": resource["id"],
        "status": "final",
        "code": observation_code,
        "value": rendered,
        "unit": unit,
    }


def _tagged(resource, code):
    meta = resource.get("meta") if isinstance(resource.get("meta"), dict) else {}
    tags = meta.get("tag") if isinstance(meta.get("tag"), list) else []
    return any(
        isinstance(tag, dict) and tag.get("system") == _TAG and tag.get("code") == code
        for tag in tags)


def _code(resource):
    coding = ((resource.get("code") or {}).get("coding") or [None])[0]
    if not isinstance(coding, dict):
        return None
    return coding.get("code")
