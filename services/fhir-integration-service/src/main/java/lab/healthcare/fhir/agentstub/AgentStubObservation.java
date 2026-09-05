package lab.healthcare.fhir.agentstub;

import lab.healthcare.fhir.patient.PatientContextSource;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotOutcome;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotResourceStatus;

/**
 * What the stub is allowed to say after consuming a v1 contract. Never includes
 * record values, Patient identifiers, tokens, or model output.
 */
public record AgentStubObservation(
        String contractVersion,
        String destination,
        PatientContextSource contextSource,
        ClinicalSnapshotOutcome outcome,
        ClinicalSnapshotResourceStatus patientStatus,
        ObservedCollection conditions,
        ObservedCollection observations,
        ObservedCollection diagnosticReports,
        ObservedCollection medicationRequests,
        boolean consumed,
        boolean modelCalled) {

    public AgentStubObservation {
        if (outcome == null) {
            throw new IllegalArgumentException("Agent stub outcome must be provided");
        }
        contractVersion = contractVersion == null ? "" : contractVersion.trim();
        destination = destination == null ? "" : destination.trim();
        if (modelCalled) {
            throw new IllegalArgumentException("Task 045 agent stub must not call a model");
        }
    }

    @Override
    public String toString() {
        return "AgentStubObservation[contractVersion="
                + contractVersion
                + ", outcome="
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
                + ", consumed="
                + consumed
                + ", modelCalled="
                + modelCalled
                + "]";
    }

    private static String collectionLine(ObservedCollection collection) {
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
