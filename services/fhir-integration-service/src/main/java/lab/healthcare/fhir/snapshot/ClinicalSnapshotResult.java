package lab.healthcare.fhir.snapshot;

import lab.healthcare.fhir.patient.PatientContextSource;

import java.time.Instant;

/**
 * Laboratory diagnosis of a controlled clinical snapshot. Never includes
 * tokens, Patient identifiers, FHIR JSON, or clinical values.
 */
public record ClinicalSnapshotResult(
        ClinicalSnapshotOutcome outcome,
        String destination,
        PatientContextSource contextSource,
        Instant generatedAt,
        ClinicalSnapshotResourceStatus patientStatus,
        ClinicalSnapshotResourceStatus conditionStatus,
        Integer conditionCount,
        ClinicalSnapshotResourceStatus observationStatus,
        Integer observationCount,
        ClinicalSnapshotResourceStatus diagnosticReportStatus,
        Integer diagnosticReportCount,
        ClinicalSnapshotResourceStatus medicationRequestStatus,
        Integer medicationRequestCount,
        String detail) {

    public ClinicalSnapshotResult {
        if (outcome == null) {
            throw new IllegalArgumentException("Clinical snapshot outcome must be provided");
        }
        destination = destination == null ? "" : destination.trim();
        detail = detail == null ? "" : detail.trim();
    }

    public static ClinicalSnapshotResult authenticationRequired(String destination, String detail) {
        return new ClinicalSnapshotResult(
                ClinicalSnapshotOutcome.AUTHENTICATION_REQUIRED,
                destination,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                detail);
    }

    public static ClinicalSnapshotResult contextNotConfigured(String destination) {
        return new ClinicalSnapshotResult(
                ClinicalSnapshotOutcome.PATIENT_CONTEXT_NOT_CONFIGURED,
                destination,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                "Sandbox Patient context is not configured");
    }

    public static ClinicalSnapshotResult unavailable(
            String destination,
            Instant generatedAt,
            ClinicalSnapshotResourceStatus patientStatus,
            String detail) {
        return new ClinicalSnapshotResult(
                ClinicalSnapshotOutcome.SNAPSHOT_UNAVAILABLE,
                destination,
                PatientContextSource.CONFIGURED,
                generatedAt,
                patientStatus,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                detail);
    }

    @Override
    public String toString() {
        return "ClinicalSnapshotResult[outcome="
                + outcome
                + ", destination="
                + destination
                + ", contextSource="
                + (contextSource == null ? "" : contextSource.name())
                + ", generatedAt="
                + (generatedAt == null ? "" : generatedAt)
                + ", patientStatus="
                + patientStatus
                + ", conditionStatus="
                + conditionStatus
                + ", conditionCount="
                + conditionCount
                + ", observationStatus="
                + observationStatus
                + ", observationCount="
                + observationCount
                + ", diagnosticReportStatus="
                + diagnosticReportStatus
                + ", diagnosticReportCount="
                + diagnosticReportCount
                + ", medicationRequestStatus="
                + medicationRequestStatus
                + ", medicationRequestCount="
                + medicationRequestCount
                + "]";
    }
}
