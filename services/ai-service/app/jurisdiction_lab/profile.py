"""Closed demonstration profiles. The process selects one. The model cannot."""
from dataclasses import dataclass

from app.enterprise_llm_providers.errors import ProviderError


OPERATION_ID = "jurisdiction-lab-summary-v1"
VALIDATION_CLASS = "internal-demo-rules"
LOINC = "http://loinc.org"
UCUM = "http://unitsofmeasure.org"
PROFILE_TAG = "https://lab.local/jurisdiction/profile"
VERSION_TAG = "https://lab.local/jurisdiction/profile-version"
VALIDATION_TAG = "https://lab.local/jurisdiction/validation"
CALLER_SYSTEM = "mini-his"
CALLER_ORGANIZATION = "org-mini-his"


@dataclass(frozen=True, slots=True)
class LabQuantity:
    resource_id: str
    code: str
    value: str
    unit: str


@dataclass(frozen=True, slots=True)
class JurisdictionProfile:
    profile_id: str
    version: str
    jurisdiction: str
    fhir_version: str
    guide_name: str
    guide_version: str
    guide_status: str
    guide_url: str
    informative_reference: str
    organization_id: str
    policy_ref: str
    source_key: str
    authorization_id: str
    patient_system: str
    patient_value: str
    logical_id: str
    base_url: str
    observations: tuple


def _profile(**values):
    return JurisdictionProfile(**values)


PERU = _profile(
    profile_id="pe-lab-demo-v1", version="v1", jurisdiction="PE", fhir_version="4.0.1",
    guide_name="hl7.fhir.pe.CorePE", guide_version="0.1", guide_status="draft",
    guide_url="https://www.gob.pe/minsa/RENHICE/fhir/ImplementationGuide/hl7.fhir.pe.CorePE",
    informative_reference="CorePE 0.1 is a draft. This profile does not validate that guide.",
    organization_id="org-pe-lab-demo", policy_ref="pe-lab-demo-policy-v1", source_key="pe-lab-demo",
    authorization_id="pe-lab-demo-001", patient_system="https://lab.local/jurisdiction/pe/patient",
    patient_value="PE-PAT-001", logical_id="pe-pat-001", base_url="https://lab.local/jurisdiction/pe",
    observations=(
        LabQuantity("pe-obs-718-7", "718-7", "13.4", "g/dL"),
        LabQuantity("pe-obs-6690-2", "6690-2", "6.2", "10*3/uL"),
    ))
SPAIN = _profile(
    profile_id="es-lab-demo-v1", version="v1", jurisdiction="ES", fhir_version="4.0.1",
    guide_name="hl7.fhir.eu.base", guide_version="2.0.0", guide_status="informative",
    guide_url="http://hl7.eu/fhir/base/ImplementationGuide/hl7.fhir.eu.base",
    informative_reference="HL7 Europe Base 2.0.0 is superseded by 2.0.1. IPS 2.0.1 is informative only.",
    organization_id="org-es-lab-demo", policy_ref="es-lab-demo-policy-v1", source_key="es-lab-demo",
    authorization_id="es-lab-demo-001", patient_system="https://lab.local/jurisdiction/es/patient",
    patient_value="ES-PAT-001", logical_id="es-pat-001", base_url="https://lab.local/jurisdiction/es",
    observations=(
        LabQuantity("es-obs-2345-7", "2345-7", "90", "mg/dL"),
        LabQuantity("es-obs-4544-3", "4544-3", "42", "%"),
    ))
PROFILES = {PERU.profile_id: PERU, SPAIN.profile_id: SPAIN}


def require_profile(profile_id):
    """Resolve one server-selected profile. An absent id and an unknown version stay distinct."""
    if type(profile_id) is not str or profile_id == "":
        raise ProviderError("profile_unknown")
    profile = PROFILES.get(profile_id)
    if profile is not None:
        return profile
    if profile_id.startswith("pe-lab-demo-") or profile_id.startswith("es-lab-demo-"):
        raise ProviderError("profile_version_unavailable")
    raise ProviderError("profile_unknown")
