package lab.healthcare.fhir.routing;

import lab.healthcare.fhir.exception.FhirErrorCategory;
import lab.healthcare.fhir.patient.PatientContextSource;

/**
 * Laboratory diagnosis of an authenticated DiagnosticReport search. Never includes
 * tokens, Patient identifiers, DiagnosticReport JSON, or report contents.
 */
public record FhirDiagnosticReportSearchResult(
        FhirDiagnosticReportSearchOutcome outcome,
        String destination,
        String resourceType,
        String responseType,
        Integer httpStatus,
        FhirErrorCategory dependencyCategory,
        PatientContextSource contextSource,
        Boolean hasPatientContext,
        Boolean hasEntries,
        String detail) {

    public FhirDiagnosticReportSearchResult {
        if (outcome == null) {
            throw new IllegalArgumentException("DiagnosticReport search outcome must be provided");
        }
        destination = destination == null ? "" : destination.trim();
        resourceType = resourceType == null ? "" : resourceType.trim();
        responseType = responseType == null ? "" : responseType.trim();
        detail = detail == null ? "" : detail.trim();
    }

    public static FhirDiagnosticReportSearchResult authenticationRequired(String destination, String detail) {
        return new FhirDiagnosticReportSearchResult(
                FhirDiagnosticReportSearchOutcome.AUTHENTICATION_REQUIRED,
                destination,
                "DiagnosticReport",
                "",
                null,
                FhirErrorCategory.AUTHENTICATION_ERROR,
                null,
                null,
                null,
                detail);
    }

    public static FhirDiagnosticReportSearchResult contextNotConfigured(String destination) {
        return new FhirDiagnosticReportSearchResult(
                FhirDiagnosticReportSearchOutcome.PATIENT_CONTEXT_NOT_CONFIGURED,
                destination,
                "DiagnosticReport",
                "",
                null,
                FhirErrorCategory.VALIDATION_ERROR,
                null,
                false,
                null,
                "Sandbox Patient context is not configured");
    }

    public static FhirDiagnosticReportSearchResult capabilityUnsupported(
            String destination, String resourceType, String interaction) {
        return new FhirDiagnosticReportSearchResult(
                FhirDiagnosticReportSearchOutcome.CAPABILITY_UNSUPPORTED,
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
        return "FhirDiagnosticReportSearchResult[outcome="
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
