"""Minimize one jurisdiction envelope. Evidence comes from the resources, not from model text."""
import json
import re

from app.enterprise_llm_providers.errors import ProviderError

from .profile import (
    LOINC, OPERATION_ID, PROFILE_TAG, UCUM, VALIDATION_CLASS, VALIDATION_TAG, VERSION_TAG,
)


_ID = re.compile(r"[A-Za-z0-9\-.]{1,64}")
_NUMBER = re.compile(r"[0-9]+(?:\.[0-9]+)?")
_OFFICIAL = ("gob.pe", "hl7.eu", "hl7.org/fhir/uv/ips")
_DEMOGRAPHIC = ("name", "birthDate", "address", "telecom")
_CHART_KEYS = {
    "operation_id", "patient_id", "profile_id", "profile_version",
    "validation_class", "official_conformance", "facts",
}
_FACT_KEYS = {
    "source", "resourceType", "id", "status", "code", "value", "unit",
    "ucum_system", "provenance_ref",
}


def minimize_envelope(envelope, profile):
    if not isinstance(envelope, dict) or envelope.get("status") != "complete" or envelope.get("truncated") is not False:
        raise ProviderError("context_rejected")
    sources = envelope.get("sources")
    if not isinstance(sources, list) or len(sources) != 1 or not isinstance(sources[0], dict):
        raise ProviderError("cross_border_denied" if _several(sources) else "context_rejected")
    source = sources[0]
    if source.get("sourceKey") != profile.source_key:
        raise ProviderError("jurisdiction_mismatch")
    if source.get("organizationId") != profile.organization_id or source.get("outcome") != "complete":
        raise ProviderError("organization_mismatch" if source.get("organizationId") != profile.organization_id else "context_rejected")
    entries = envelope.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ProviderError("context_incomplete")
    facts = []
    seen_patient = False
    for entry in entries:
        resource = entry.get("resource") if isinstance(entry, dict) else None
        if not isinstance(resource, dict) or not isinstance(resource.get("resourceType"), str):
            raise ProviderError("response_rejected")
        if entry.get("sourceKey") != profile.source_key or entry.get("organizationId") != profile.organization_id:
            raise ProviderError("organization_mismatch")
        _reject_official(resource)
        if resource["resourceType"] == "Patient":
            _patient(resource, profile)
            seen_patient = True
            continue
        if resource["resourceType"] != "Observation":
            continue
        if _longitudinal_series(resource):
            continue
        facts.append(_observation(entry, resource, profile))
    if not seen_patient or len(facts) != len(profile.observations):
        raise ProviderError("context_incomplete")
    chart = {
        "operation_id": OPERATION_ID,
        "patient_id": profile.patient_value,
        "profile_id": profile.profile_id,
        "profile_version": profile.version,
        "validation_class": VALIDATION_CLASS,
        "official_conformance": False,
        "facts": facts,
    }
    return require_model_context(chart, profile)


def require_model_context(chart, profile):
    if not isinstance(chart, dict) or set(chart) != _CHART_KEYS:
        raise ProviderError("context_rejected")
    if (chart["operation_id"] != OPERATION_ID or chart["patient_id"] != profile.patient_value
            or chart["profile_id"] != profile.profile_id or chart["profile_version"] != profile.version
            or chart["validation_class"] != VALIDATION_CLASS or chart["official_conformance"] is not False):
        raise ProviderError("jurisdiction_mismatch")
    facts = chart["facts"]
    if not isinstance(facts, list) or len(facts) != len(profile.observations):
        raise ProviderError("context_incomplete")
    expected = {item.resource_id: item for item in profile.observations}
    seen = set()
    for fact in facts:
        if not isinstance(fact, dict) or set(fact) != _FACT_KEYS:
            raise ProviderError("context_rejected")
        item = expected.get(fact["id"])
        if (item is None or fact["source"] != profile.source_key or fact["resourceType"] != "Observation"
                or fact["status"] != "final" or fact["code"] != item.code or fact["value"] != item.value
                or fact["unit"] != item.unit or fact["ucum_system"] != UCUM):
            raise ProviderError("context_rejected")
        prefix = profile.base_url + "/Observation/" + item.resource_id
        if fact["provenance_ref"] != prefix or fact["id"] in seen:
            raise ProviderError("context_rejected")
        seen.add(fact["id"])
    rendered = json.dumps(chart, ensure_ascii=True)
    if any(token in rendered for token in _DEMOGRAPHIC) or "official-conformance" in rendered:
        raise ProviderError("context_rejected")
    return chart


def validate_summary(chart, parsed, profile):
    if not isinstance(parsed, dict) or set(parsed) != {"kind", "statements", "review"}:
        raise ProviderError("invalid_output")
    if parsed["kind"] != OPERATION_ID or parsed["review"] != "pending_human_review":
        raise ProviderError("invalid_output")
    statements = parsed["statements"]
    if not isinstance(statements, list) or not statements or len(statements) > 8:
        raise ProviderError("invalid_output")
    known = {(item["source"], item["id"]): item for item in chart["facts"]}
    checked = []
    cited = set()
    for item in statements:
        if not isinstance(item, dict) or set(item) != {"text", "sources"}:
            raise ProviderError("invalid_output")
        text = item["text"]
        if type(text) is not str or text.strip() == "" or len(text) > 400:
            raise ProviderError("invalid_output")
        sources = item["sources"]
        if not isinstance(sources, list) or not sources or len(sources) > 4:
            raise ProviderError("invalid_output")
        kept = []
        for source in sources:
            if not isinstance(source, dict) or set(source) != {"source", "resourceType", "id"}:
                raise ProviderError("invalid_output")
            fact = known.get((source["source"], source["id"]))
            if fact is None or fact["value"] not in text:
                raise ProviderError("invalid_output")
            cited.add(fact["id"])
            kept.append({"source": fact["source"], "resourceType": "Observation", "id": fact["id"]})
        checked.append({"text": text, "sources": kept})
    if cited != {item.resource_id for item in profile.observations}:
        raise ProviderError("invalid_output")
    return {"kind": OPERATION_ID, "review": "pending_human_review", "statements": checked}


def _several(sources):
    if not isinstance(sources, list):
        return False
    keys = [item.get("sourceKey") for item in sources if isinstance(item, dict)]
    return sum(key in {"pe-lab-demo", "es-lab-demo"} for key in keys) > 1


def _longitudinal_series(resource):
    meta = resource.get("meta") if isinstance(resource.get("meta"), dict) else {}
    tags = meta.get("tag") if isinstance(meta.get("tag"), list) else []
    return any(
        isinstance(tag, dict) and tag.get("system") == VALIDATION_TAG and tag.get("code") == "longitudinal-series"
        for tag in tags)


def _reject_official(resource):
    profiles = (resource.get("meta") or {}).get("profile") if isinstance(resource.get("meta"), dict) else None
    if isinstance(profiles, list) and any(isinstance(item, str) and any(token in item for token in _OFFICIAL) for item in profiles):
        raise ProviderError("profile_not_verified")


def _patient(resource, profile):
    if resource.get("id") != profile.logical_id:
        raise ProviderError("context_rejected")
    if any(key in resource for key in _DEMOGRAPHIC):
        raise ProviderError("context_rejected")
    identifiers = resource.get("identifier")
    if not isinstance(identifiers, list) or len(identifiers) != 1:
        raise ProviderError("context_incomplete")
    identifier = identifiers[0]
    if not isinstance(identifier, dict) or identifier.get("system") != profile.patient_system or identifier.get("value") != profile.patient_value:
        raise ProviderError("context_rejected")
    _tags(resource, profile, observation=False)


def _observation(entry, resource, profile):
    if resource.get("status") != "final":
        raise ProviderError("context_incomplete")
    reference = (resource.get("subject") or {}).get("reference") if isinstance(resource.get("subject"), dict) else None
    expected = profile.base_url + "/Patient/" + profile.logical_id
    if reference != expected:
        raise ProviderError("context_rejected" if isinstance(reference, str) and "Patient/" in reference else "context_incomplete")
    coding = ((resource.get("code") or {}).get("coding") or [None])[0]
    quantity = resource.get("valueQuantity")
    if not isinstance(coding, dict) or coding.get("system") != LOINC or not isinstance(quantity, dict):
        raise ProviderError("context_incomplete")
    if quantity.get("system") != UCUM or quantity.get("unit") != quantity.get("code"):
        raise ProviderError("context_rejected")
    _tags(resource, profile, observation=True)
    value = quantity.get("value")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProviderError("context_incomplete")
    rendered = format(value, "g")
    if _NUMBER.fullmatch(rendered) is None or _ID.fullmatch(str(resource.get("id") or "")) is None:
        raise ProviderError("context_rejected")
    full_url = entry.get("fullUrl")
    provenance = profile.base_url + "/Observation/" + resource["id"]
    if full_url != provenance:
        raise ProviderError("context_rejected")
    return {
        "source": profile.source_key,
        "resourceType": "Observation",
        "id": resource["id"],
        "status": "final",
        "code": coding.get("code"),
        "value": rendered,
        "unit": quantity.get("code"),
        "ucum_system": UCUM,
        "provenance_ref": provenance,
    }


def _tags(resource, profile, observation):
    meta = resource.get("meta") if isinstance(resource.get("meta"), dict) else {}
    if meta.get("source") != profile.source_key:
        raise ProviderError("jurisdiction_mismatch")
    tags = meta.get("tag") if isinstance(meta.get("tag"), list) else []
    found = {(tag.get("system"), tag.get("code")) for tag in tags if isinstance(tag, dict)}
    declared = [code for system, code in found if system == PROFILE_TAG]
    if declared and declared[0] != profile.profile_id:
        raise ProviderError("jurisdiction_mismatch")
    required = {
        (PROFILE_TAG, profile.profile_id),
        (VERSION_TAG, profile.version),
        (VALIDATION_TAG, VALIDATION_CLASS),
        (VALIDATION_TAG, "fhir-r4-checked"),
    }
    if observation:
        required.add((VALIDATION_TAG, "quantity-verified"))
    if not required.issubset(found):
        raise ProviderError("profile_not_verified")
    if any(code in {"official-conformance", "national-conformance"} for _system, code in found):
        raise ProviderError("profile_not_verified")
