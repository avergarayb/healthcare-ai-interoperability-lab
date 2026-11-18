"""Deterministic comparison of two dated quantities. The model does not calculate."""
from decimal import Decimal, ROUND_HALF_EVEN
import re

from app.enterprise_llm_providers.errors import ProviderError
from app.jurisdiction_lab.profile import (
    LOINC, PROFILE_TAG, UCUM, VALIDATION_CLASS, VALIDATION_TAG, VERSION_TAG,
)

from .series import OPERATION_ID, TAG, series_for


_INSTANT = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z")
_NUMBER = re.compile(r"[0-9]+(?:\.[0-9]+)?")
_CHART_KEYS = {
    "operation_id", "profile_id", "profile_version", "validation_class", "official_conformance",
    "jurisdiction", "code", "code_system", "unit", "ucum_system",
    "prior_value", "recent_value", "prior_date", "recent_date",
    "absolute_difference", "direction", "percent_difference",
    "prior_reference", "recent_reference", "source", "specimen", "method", "comparability",
}


def collect_observations(envelope, profile):
    """Return tagged series resources. Untagged seed observations stay out of this list."""
    _gate(envelope, profile)
    found = []
    seen_patient = False
    for entry in envelope["entries"]:
        if not isinstance(entry, dict):
            raise ProviderError("response_rejected")
        resource = entry.get("resource")
        if not isinstance(resource, dict) or not isinstance(resource.get("resourceType"), str):
            raise ProviderError("response_rejected")
        if entry.get("sourceKey") != profile.source_key or entry.get("organizationId") != profile.organization_id:
            raise ProviderError(
                "jurisdiction_mismatch" if entry.get("sourceKey") != profile.source_key else "organization_mismatch")
        if resource["resourceType"] == "Patient":
            _patient(resource, profile)
            seen_patient = True
            continue
        if resource["resourceType"] != "Observation" or not _tagged(resource):
            continue
        found.append(entry)
    if not seen_patient:
        raise ProviderError("context_incomplete")
    return found


def compare_points(found, profile):
    """Compare one closed pair. Same code and unit are not enough."""
    spec = series_for(profile)
    if not isinstance(found, list):
        raise ProviderError("context_rejected")
    if len(found) != 2:
        raise ProviderError("ambiguous_duplicate" if len(found) > 2 else "context_incomplete")
    points = [_point(entry, profile, spec) for entry in found]
    if points[0]["id"] == points[1]["id"] or points[0]["effective"] == points[1]["effective"]:
        raise ProviderError("ambiguous_duplicate")
    expected = {spec.prior.resource_id, spec.recent.resource_id}
    if {points[0]["id"], points[1]["id"]} != expected:
        raise ProviderError("ambiguous_duplicate")
    if points[0]["code"] != spec.code or points[1]["code"] != spec.code:
        raise ProviderError("code_mismatch")
    if points[0]["unit"] != points[1]["unit"] or points[0]["unit"] != spec.unit:
        raise ProviderError("unit_mismatch")
    if points[0]["specimen"] != points[1]["specimen"] or points[0]["specimen"] != spec.specimen:
        raise ProviderError("context_rejected")
    if (points[0]["method_system"] != points[1]["method_system"]
            or points[0]["method_code"] != points[1]["method_code"]
            or points[0]["method_system"] != spec.method_system
            or points[0]["method_code"] != spec.method_code):
        raise ProviderError("context_rejected")
    ordered = sorted(points, key=lambda item: item["effective"])
    prior, recent = ordered
    delta = recent["amount"] - prior["amount"]
    if prior["amount"] == 0:
        raise ProviderError("zero_baseline")
    percent = (delta / prior["amount"] * Decimal("100")).quantize(Decimal("0.0001"), rounding=ROUND_HALF_EVEN)
    direction = "aumento" if delta > 0 else "disminucion" if delta < 0 else "sin cambio"
    chart = {
        "operation_id": OPERATION_ID,
        "profile_id": profile.profile_id,
        "profile_version": profile.version,
        "validation_class": VALIDATION_CLASS,
        "official_conformance": False,
        "jurisdiction": profile.jurisdiction,
        "code": spec.code,
        "code_system": LOINC,
        "unit": spec.unit,
        "ucum_system": UCUM,
        "prior_value": _plain(prior["amount"]),
        "recent_value": _plain(recent["amount"]),
        "prior_date": prior["effective"],
        "recent_date": recent["effective"],
        "absolute_difference": _signed(delta),
        "direction": direction,
        "percent_difference": _signed(percent),
        "prior_reference": prior["id"],
        "recent_reference": recent["id"],
        "source": profile.source_key,
        "specimen": spec.specimen,
        "method": spec.method_code,
        "comparability": "verified",
    }
    if set(chart) != _CHART_KEYS:
        raise ProviderError("context_rejected")
    evidence = {
        "organization_id": profile.organization_id,
        "patient_id": profile.patient_value,
        "jurisdiction": profile.jurisdiction,
        "profile_id": profile.profile_id,
        "profile_version": profile.version,
        "code": spec.code,
        "code_system": LOINC,
        "prior_resource_id": prior["id"],
        "recent_resource_id": recent["id"],
        "prior_date": prior["effective"],
        "recent_date": recent["effective"],
        "prior_value": chart["prior_value"],
        "recent_value": chart["recent_value"],
        "ucum_system": UCUM,
        "ucum_code": spec.unit,
        "absolute_difference": chart["absolute_difference"],
        "direction": direction,
        "percent_difference": chart["percent_difference"],
        "prior_provenance": prior["provenance"],
        "recent_provenance": recent["provenance"],
        "comparability": "verified",
        "specimen": spec.specimen,
        "method": spec.method_code,
    }
    return chart, evidence


def compare_envelope(envelope, profile):
    return compare_points(collect_observations(envelope, profile), profile)


def _gate(envelope, profile):
    if not isinstance(envelope, dict):
        raise ProviderError("context_rejected")
    status = envelope.get("status")
    if status == "partial" or envelope.get("truncated") is not False:
        raise ProviderError("context_incomplete")
    if status != "complete":
        raise ProviderError("context_rejected")
    sources = envelope.get("sources")
    if not isinstance(sources, list):
        raise ProviderError("context_rejected")
    keys = [item.get("sourceKey") for item in sources if isinstance(item, dict)]
    if sum(key in {"pe-lab-demo", "es-lab-demo"} for key in keys) > 1:
        raise ProviderError("cross_border_denied")
    if len(sources) != 1 or not isinstance(sources[0], dict):
        raise ProviderError("context_rejected")
    source = sources[0]
    if source.get("sourceKey") != profile.source_key:
        raise ProviderError("jurisdiction_mismatch")
    if source.get("organizationId") != profile.organization_id or source.get("outcome") != "complete":
        raise ProviderError("organization_mismatch" if source.get("organizationId") != profile.organization_id else "context_rejected")
    if not isinstance(envelope.get("entries"), list) or not envelope["entries"]:
        raise ProviderError("context_incomplete")


def _patient(resource, profile):
    identifiers = resource.get("identifier")
    if not isinstance(identifiers, list) or len(identifiers) != 1 or not isinstance(identifiers[0], dict):
        raise ProviderError("context_incomplete")
    if identifiers[0].get("system") != profile.patient_system or identifiers[0].get("value") != profile.patient_value:
        raise ProviderError("patient_mismatch")
    if resource.get("id") != profile.logical_id:
        raise ProviderError("patient_mismatch")


def _tagged(resource):
    meta = resource.get("meta") if isinstance(resource.get("meta"), dict) else {}
    tags = meta.get("tag") if isinstance(meta.get("tag"), list) else []
    return any(isinstance(tag, dict) and tag.get("system") == VALIDATION_TAG and tag.get("code") == TAG for tag in tags)


def _point(entry, profile, spec):
    resource = entry["resource"]
    if resource.get("status") != "final":
        raise ProviderError("status_rejected")
    subject = resource.get("subject") if isinstance(resource.get("subject"), dict) else {}
    expected_subject = profile.base_url + "/Patient/" + profile.logical_id
    if subject.get("reference") != expected_subject:
        raise ProviderError("patient_mismatch")
    coding = ((resource.get("code") or {}).get("coding") or [None])[0] if isinstance(resource.get("code"), dict) else None
    if not isinstance(coding, dict) or not isinstance(coding.get("system"), str):
        raise ProviderError("context_incomplete")
    if coding.get("system") != LOINC:
        raise ProviderError("code_system_mismatch")
    if coding.get("code") != spec.code:
        raise ProviderError("code_mismatch")
    quantity = resource.get("valueQuantity")
    if not isinstance(quantity, dict):
        raise ProviderError("value_rejected")
    if "comparator" in quantity:
        raise ProviderError("comparator_unsupported")
    if quantity.get("system") != UCUM:
        raise ProviderError("ucum_unknown")
    if quantity.get("unit") != quantity.get("code") or quantity.get("code") != spec.unit:
        raise ProviderError("unit_mismatch")
    amount = _decimal(quantity.get("value"))
    effective = _effective(resource)
    specimen = resource.get("specimen") if isinstance(resource.get("specimen"), dict) else {}
    method = resource.get("method") if isinstance(resource.get("method"), dict) else {}
    method_coding = (method.get("coding") or [None])[0] if isinstance(method.get("coding"), list) else None
    if not isinstance(specimen.get("reference"), str) or specimen.get("reference") == "":
        raise ProviderError("context_insufficient")
    if not isinstance(method_coding, dict) or not method_coding.get("system") or not method_coding.get("code"):
        raise ProviderError("context_insufficient")
    _profile_tags(resource, profile)
    provenance = profile.base_url + "/Observation/" + resource["id"]
    if entry.get("fullUrl") != provenance:
        raise ProviderError("context_rejected")
    return {
        "id": resource["id"],
        "code": coding.get("code"),
        "unit": quantity.get("code"),
        "amount": amount,
        "effective": effective,
        "specimen": specimen.get("reference"),
        "method_system": method_coding.get("system"),
        "method_code": method_coding.get("code"),
        "provenance": provenance,
    }


def _effective(resource):
    has_period = "effectivePeriod" in resource
    raw = resource.get("effectiveDateTime")
    if has_period and isinstance(raw, str):
        raise ProviderError("date_ambiguous")
    if has_period:
        raise ProviderError("date_unsupported")
    if not isinstance(raw, str) or raw == "":
        raise ProviderError("date_absent")
    if _INSTANT.fullmatch(raw) is None:
        raise ProviderError("date_unsupported")
    return raw


def _decimal(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProviderError("value_rejected")
    rendered = format(value, "g")
    if _NUMBER.fullmatch(rendered) is None:
        raise ProviderError("value_rejected")
    return Decimal(rendered)


def _profile_tags(resource, profile):
    meta = resource.get("meta") if isinstance(resource.get("meta"), dict) else {}
    if meta.get("source") != profile.source_key:
        raise ProviderError("jurisdiction_mismatch")
    tags = meta.get("tag") if isinstance(meta.get("tag"), list) else []
    found = {(tag.get("system"), tag.get("code")) for tag in tags if isinstance(tag, dict)}
    required = {
        (PROFILE_TAG, profile.profile_id),
        (VERSION_TAG, profile.version),
        (VALIDATION_TAG, VALIDATION_CLASS),
        (VALIDATION_TAG, "fhir-r4-checked"),
        (VALIDATION_TAG, "quantity-verified"),
        (VALIDATION_TAG, TAG),
    }
    if not required.issubset(found):
        raise ProviderError("profile_not_verified")


def _plain(value):
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    if text in {"", "-0", "-"}:
        return "0"
    return text


def _signed(value):
    text = _plain(value)
    if value > 0 and not text.startswith("+"):
        return "+" + text
    return text
