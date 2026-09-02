package lab.healthcare.fhir.routing;

import lab.healthcare.fhir.exception.FhirErrorCategory;

/**
 * Laboratory diagnosis of an authenticated FHIR read/search. Never includes
 * tokens, names, identifiers, or FHIR JSON.
 */
public record FhirAuthenticatedReadResult(
        FhirAuthenticatedReadOutcome outcome,
        String destination,
        String resourceType,
        String responseType,
        Integer httpStatus,
        FhirErrorCategory dependencyCategory,
        Boolean hasEntries,
        String detail) {

    public FhirAuthenticatedReadResult {
        if (outcome == null) {
            throw new IllegalArgumentException("Authenticated read outcome must be provided");
        }
        destination = destination == null ? "" : destination.trim();
        resourceType = resourceType == null ? "" : resourceType.trim();
        responseType = responseType == null ? "" : responseType.trim();
        detail = detail == null ? "" : detail.trim();
    }

    public static FhirAuthenticatedReadResult authenticationRequired(String destination, String detail) {
        return new FhirAuthenticatedReadResult(
                FhirAuthenticatedReadOutcome.AUTHENTICATION_REQUIRED,
                destination,
                "Patient",
                "",
                null,
                FhirErrorCategory.AUTHENTICATION_ERROR,
                null,
                detail);
    }

    public static FhirAuthenticatedReadResult capabilityUnsupported(
            String destination, String resourceType, String interaction) {
        return new FhirAuthenticatedReadResult(
                FhirAuthenticatedReadOutcome.CAPABILITY_UNSUPPORTED,
                destination,
                resourceType,
                "",
                null,
                FhirErrorCategory.VALIDATION_ERROR,
                null,
                "Runtime CapabilityStatement does not declare " + resourceType + " " + interaction);
    }

    @Override
    public String toString() {
        return "FhirAuthenticatedReadResult[outcome="
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
                + ", hasEntries="
                + hasEntries
                + "]";
    }
}
