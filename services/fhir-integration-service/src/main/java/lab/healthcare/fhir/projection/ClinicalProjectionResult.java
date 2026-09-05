package lab.healthcare.fhir.projection;

import lab.healthcare.fhir.patient.PatientContextSource;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotOutcome;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotResourceStatus;

import java.time.Instant;

/**
 * Laboratory diagnosis of a controlled projection. {@link #toString()} never
 * includes retained field values, Patient identifiers, tokens, or FHIR JSON.
 */
public record ClinicalProjectionResult(
        ClinicalSnapshotOutcome outcome,
        String destination,
        PatientContextSource contextSource,
        Instant generatedAt,
        ClinicalSnapshotResourceStatus patientStatus,
        RetainedPatient patient,
        ProjectedCollection<RetainedCondition> conditions,
        ProjectedCollection<RetainedObservation> observations,
        ProjectedCollection<RetainedDiagnosticReport> diagnosticReports,
        ProjectedCollection<RetainedMedicationRequest> medicationRequests,
        String detail) {

    public ClinicalProjectionResult {
        if (outcome == null) {
            throw new IllegalArgumentException("Clinical projection outcome must be provided");
        }
        destination = destination == null ? "" : destination.trim();
        detail = detail == null ? "" : detail.trim();
    }

    public static ClinicalProjectionResult authenticationRequired(String destination, String detail) {
        return new ClinicalProjectionResult(
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
                detail);
    }

    public static ClinicalProjectionResult contextNotConfigured(String destination) {
        return new ClinicalProjectionResult(
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
                "Sandbox Patient context is not configured");
    }

    public static ClinicalProjectionResult unavailable(
            String destination,
            Instant generatedAt,
            ClinicalSnapshotResourceStatus patientStatus,
            String detail) {
        return new ClinicalProjectionResult(
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
                detail);
    }

    @Override
    public String toString() {
        return "ClinicalProjectionResult[outcome="
                + outcome
                + ", destination="
                + destination
                + ", contextSource="
                + (contextSource == null ? "" : contextSource.name())
                + ", patientStatus="
                + patientStatus
                + ", conditions="
                + collectionLine(conditions)
                + ", observations="
                + collectionLine(observations)
                + ", diagnosticReports="
                + collectionLine(diagnosticReports)
                + ", medicationRequests="
                + collectionLine(medicationRequests)
                + "]";
    }

    private static String collectionLine(ProjectedCollection<?> collection) {
        if (collection == null || collection.status() == null) {
            return "";
        }
        return "status="
                + collection.status()
                + " receivedCount="
                + collection.receivedCount()
                + " retainedCount="
                + collection.retainedCount()
                + " truncated="
                + collection.truncated();
    }
}
