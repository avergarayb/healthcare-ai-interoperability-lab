package lab.healthcare.fhir.routing;

import lab.healthcare.fhir.exception.FhirErrorCategory;
import lab.healthcare.fhir.patient.PatientContextSource;

/**
 * Laboratory diagnosis of a controlled Patient read. Never includes tokens,
 * Patient identifiers, demographics, or FHIR JSON.
 */
public record FhirPatientReadResult(
        FhirPatientReadOutcome outcome,
        String destination,
        String resourceType,
        String responseType,
        Integer httpStatus,
        FhirErrorCategory dependencyCategory,
        PatientContextSource contextSource,
        Boolean hasPatientContext,
        String detail) {

    public FhirPatientReadResult {
        if (outcome == null) {
            throw new IllegalArgumentException("Patient read outcome must be provided");
        }
        destination = destination == null ? "" : destination.trim();
        resourceType = resourceType == null ? "" : resourceType.trim();
        responseType = responseType == null ? "" : responseType.trim();
        detail = detail == null ? "" : detail.trim();
    }

    public static FhirPatientReadResult authenticationRequired(String destination, String detail) {
        return new FhirPatientReadResult(
                FhirPatientReadOutcome.AUTHENTICATION_REQUIRED,
                destination,
                "Patient",
                "",
                null,
                FhirErrorCategory.AUTHENTICATION_ERROR,
                null,
                null,
                detail);
    }

    public static FhirPatientReadResult contextNotConfigured(String destination) {
        return new FhirPatientReadResult(
                FhirPatientReadOutcome.PATIENT_CONTEXT_NOT_CONFIGURED,
                destination,
                "Patient",
                "",
                null,
                FhirErrorCategory.VALIDATION_ERROR,
                null,
                false,
                "Sandbox Patient context is not configured");
    }

    public static FhirPatientReadResult capabilityUnsupported(
            String destination, String resourceType, String interaction) {
        return new FhirPatientReadResult(
                FhirPatientReadOutcome.CAPABILITY_UNSUPPORTED,
                destination,
                resourceType,
                "",
                null,
                FhirErrorCategory.VALIDATION_ERROR,
                PatientContextSource.CONFIGURED,
                true,
                "Runtime CapabilityStatement does not declare " + resourceType + " " + interaction);
    }

    @Override
    public String toString() {
        return "FhirPatientReadResult[outcome="
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
                + "]";
    }
}
