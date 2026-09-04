package lab.healthcare.fhir.routing;

import lab.healthcare.fhir.exception.FhirErrorCategory;
import lab.healthcare.fhir.patient.PatientContextSource;

/**
 * Laboratory diagnosis of an authenticated MedicationRequest search. Never includes
 * tokens, Patient identifiers, MedicationRequest JSON, or medication details.
 */
public record FhirMedicationRequestSearchResult(
        FhirMedicationRequestSearchOutcome outcome,
        String destination,
        String resourceType,
        String responseType,
        Integer httpStatus,
        FhirErrorCategory dependencyCategory,
        PatientContextSource contextSource,
        Boolean hasPatientContext,
        Boolean hasEntries,
        String detail) {

    public FhirMedicationRequestSearchResult {
        if (outcome == null) {
            throw new IllegalArgumentException("MedicationRequest search outcome must be provided");
        }
        destination = destination == null ? "" : destination.trim();
        resourceType = resourceType == null ? "" : resourceType.trim();
        responseType = responseType == null ? "" : responseType.trim();
        detail = detail == null ? "" : detail.trim();
    }

    public static FhirMedicationRequestSearchResult authenticationRequired(String destination, String detail) {
        return new FhirMedicationRequestSearchResult(
                FhirMedicationRequestSearchOutcome.AUTHENTICATION_REQUIRED,
                destination,
                "MedicationRequest",
                "",
                null,
                FhirErrorCategory.AUTHENTICATION_ERROR,
                null,
                null,
                null,
                detail);
    }

    public static FhirMedicationRequestSearchResult contextNotConfigured(String destination) {
        return new FhirMedicationRequestSearchResult(
                FhirMedicationRequestSearchOutcome.PATIENT_CONTEXT_NOT_CONFIGURED,
                destination,
                "MedicationRequest",
                "",
                null,
                FhirErrorCategory.VALIDATION_ERROR,
                null,
                false,
                null,
                "Sandbox Patient context is not configured");
    }

    public static FhirMedicationRequestSearchResult capabilityUnsupported(
            String destination, String resourceType, String interaction) {
        return new FhirMedicationRequestSearchResult(
                FhirMedicationRequestSearchOutcome.CAPABILITY_UNSUPPORTED,
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
        return "FhirMedicationRequestSearchResult[outcome="
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
