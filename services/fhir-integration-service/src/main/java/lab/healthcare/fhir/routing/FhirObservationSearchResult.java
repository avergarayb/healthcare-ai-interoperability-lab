package lab.healthcare.fhir.routing;

import lab.healthcare.fhir.exception.FhirErrorCategory;
import lab.healthcare.fhir.patient.PatientContextSource;

/**
 * Laboratory diagnosis of an authenticated Observation search. Never includes
 * tokens, Patient identifiers, Observation JSON, or clinical values.
 */
public record FhirObservationSearchResult(
        FhirObservationSearchOutcome outcome,
        String destination,
        String resourceType,
        String responseType,
        Integer httpStatus,
        FhirErrorCategory dependencyCategory,
        PatientContextSource contextSource,
        Boolean hasPatientContext,
        Boolean hasEntries,
        String detail) {

    public FhirObservationSearchResult {
        if (outcome == null) {
            throw new IllegalArgumentException("Observation search outcome must be provided");
        }
        destination = destination == null ? "" : destination.trim();
        resourceType = resourceType == null ? "" : resourceType.trim();
        responseType = responseType == null ? "" : responseType.trim();
        detail = detail == null ? "" : detail.trim();
    }

    public static FhirObservationSearchResult authenticationRequired(String destination, String detail) {
        return new FhirObservationSearchResult(
                FhirObservationSearchOutcome.AUTHENTICATION_REQUIRED,
                destination,
                "Observation",
                "",
                null,
                FhirErrorCategory.AUTHENTICATION_ERROR,
                null,
                null,
                null,
                detail);
    }

    public static FhirObservationSearchResult contextNotConfigured(String destination) {
        return new FhirObservationSearchResult(
                FhirObservationSearchOutcome.PATIENT_CONTEXT_NOT_CONFIGURED,
                destination,
                "Observation",
                "",
                null,
                FhirErrorCategory.VALIDATION_ERROR,
                null,
                false,
                null,
                "Sandbox Patient context is not configured");
    }

    public static FhirObservationSearchResult capabilityUnsupported(
            String destination, String resourceType, String interaction) {
        return new FhirObservationSearchResult(
                FhirObservationSearchOutcome.CAPABILITY_UNSUPPORTED,
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
        return "FhirObservationSearchResult[outcome="
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
