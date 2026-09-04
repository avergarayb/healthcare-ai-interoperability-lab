package lab.healthcare.fhir.routing;

import lab.healthcare.fhir.exception.FhirErrorCategory;
import lab.healthcare.fhir.patient.PatientContextSource;

/**
 * Laboratory diagnosis of an authenticated Condition search. Never includes
 * tokens, Patient identifiers, Condition JSON, or clinical codes.
 */
public record FhirConditionSearchResult(
        FhirConditionSearchOutcome outcome,
        String destination,
        String resourceType,
        String responseType,
        Integer httpStatus,
        FhirErrorCategory dependencyCategory,
        PatientContextSource contextSource,
        Boolean hasPatientContext,
        Boolean hasEntries,
        String detail) {

    public FhirConditionSearchResult {
        if (outcome == null) {
            throw new IllegalArgumentException("Condition search outcome must be provided");
        }
        destination = destination == null ? "" : destination.trim();
        resourceType = resourceType == null ? "" : resourceType.trim();
        responseType = responseType == null ? "" : responseType.trim();
        detail = detail == null ? "" : detail.trim();
    }

    public static FhirConditionSearchResult authenticationRequired(String destination, String detail) {
        return new FhirConditionSearchResult(
                FhirConditionSearchOutcome.AUTHENTICATION_REQUIRED,
                destination,
                "Condition",
                "",
                null,
                FhirErrorCategory.AUTHENTICATION_ERROR,
                null,
                null,
                null,
                detail);
    }

    public static FhirConditionSearchResult contextNotConfigured(String destination) {
        return new FhirConditionSearchResult(
                FhirConditionSearchOutcome.PATIENT_CONTEXT_NOT_CONFIGURED,
                destination,
                "Condition",
                "",
                null,
                FhirErrorCategory.VALIDATION_ERROR,
                null,
                false,
                null,
                "Sandbox Patient context is not configured");
    }

    public static FhirConditionSearchResult capabilityUnsupported(
            String destination, String resourceType, String interaction) {
        return new FhirConditionSearchResult(
                FhirConditionSearchOutcome.CAPABILITY_UNSUPPORTED,
                destination,
                resourceType,
                "",
                null,
                FhirErrorCategory.VALIDATION_ERROR,
                PatientContextSource.CONFIGURED,
                true,
                null,
                "Runtime CapabilityStatement does not declare " + resourceType + " " + interaction);
    }

    @Override
    public String toString() {
        return "FhirConditionSearchResult[outcome="
                + outcome
                + ", destination="
                + destination
                + ", resourceType="
                + resourceType
                + ", responseType="
                + responseType
                + ", httpStatus="
                + httpStatus
                + ", dependencyCategory="
                + (dependencyCategory == null ? "" : dependencyCategory.name())
                + ", contextSource="
                + (contextSource == null ? "" : contextSource.name())
                + ", hasPatientContext="
                + hasPatientContext
                + ", hasEntries="
                + hasEntries
                + "]";
    }
}
