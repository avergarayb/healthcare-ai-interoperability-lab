"""Closed permit for one external synthetic FHIR chart. It does not widen lab-result-summary-v1."""

OPERATION_ID = "external-fhir-lab-summary-v1"
POLICY_REF = "external-fhir-lab-summary-policy-v1"
PATIENT_ID = "EXT-PAT-001"
SOURCE = "smart-sandbox"
IDENTIFIER_SYSTEM = "https://lab.local/external-fhir/patient"
CALLER_SYSTEM = "mini-his"
ORGANIZATION_ID = "org-smart-sandbox"
AUTHORIZATION_ID = "external-fhir-001"
DEPLOYMENT_ID = "gemini-sdk-a"
REAL_SEND_ARMED = False


def request_real_provider_send():
    """Live provider delivery stays closed until a later authorization changes this function."""
    from app.enterprise_llm_providers.errors import ProviderError
    if REAL_SEND_ARMED is False:
        raise ProviderError("provider_send_blocked")
    raise ProviderError("provider_send_blocked")
