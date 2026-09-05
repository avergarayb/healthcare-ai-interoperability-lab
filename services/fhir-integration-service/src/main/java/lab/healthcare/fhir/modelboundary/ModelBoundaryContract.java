package lab.healthcare.fhir.modelboundary;

import lab.healthcare.fhir.patient.PatientContextSource;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotOutcome;

import java.time.Instant;

/**
 * Vendor-neutral v1 model boundary. {@link #toString()} never includes record
 * values, Patient identifiers, tokens, or FHIR JSON. This is not model input
 * and does not call a model.
 */
public record ModelBoundaryContract(
        String contractVersion,
        String destination,
        PatientContextSource contextSource,
        Instant generatedAt,
        ClinicalSnapshotOutcome outcome,
        BoundaryPatient patient,
        BoundaryCollection<BoundaryCondition> conditions,
        BoundaryCollection<BoundaryObservation> observations,
        BoundaryCollection<BoundaryDiagnosticReport> diagnosticReports,
        BoundaryCollection<BoundaryMedicationRequest> medicationRequests) {

    public ModelBoundaryContract {
        if (outcome == null) {
            throw new IllegalArgumentException("Model boundary outcome must be provided");
        }
        contractVersion = contractVersion == null || contractVersion.isBlank()
                ? ModelBoundaryContractVersion.V1
                : contractVersion.trim();
        destination = destination == null ? "" : destination.trim();
    }

    @Override
    public String toString() {
        return "ModelBoundaryContract[contractVersion="
                + contractVersion
                + ", outcome="
                + outcome
                + ", destination="
                + destination
                + ", contextSource="
                + (contextSource == null ? "" : contextSource.name())
                + ", patientStatus="
                + (patient == null ? "" : patient.status())
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

    private static String collectionLine(BoundaryCollection<?> collection) {
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
