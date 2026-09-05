package lab.healthcare.fhir.agentstub;

import lab.healthcare.fhir.modelboundary.BoundaryCollection;
import lab.healthcare.fhir.modelboundary.ModelBoundaryContract;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotResourceStatus;

/**
 * Consumes a v1 model-boundary contract and stops. Does not fetch FHIR, call a
 * model, or republish retained record values.
 */
public final class AgentStub {

    private AgentStub() {
    }

    public static AgentStubObservation observe(ModelBoundaryContract contract) {
        if (contract == null) {
            throw new IllegalArgumentException("Model boundary contract must be provided");
        }
        return new AgentStubObservation(
                contract.contractVersion(),
                contract.destination(),
                contract.contextSource(),
                contract.outcome(),
                contract.patient() == null ? null : contract.patient().status(),
                collection(contract.conditions()),
                collection(contract.observations()),
                collection(contract.diagnosticReports()),
                collection(contract.medicationRequests()),
                true,
                false);
    }

    private static ObservedCollection collection(BoundaryCollection<?> source) {
        if (source == null) {
            return null;
        }
        if (source.status() == ClinicalSnapshotResourceStatus.SUCCESS
                && source.retainedCount() != null
                && source.records() != null
                && source.records().size() != source.retainedCount()) {
            throw new IllegalStateException("Retained count does not match consumed record size");
        }
        return new ObservedCollection(
                source.status(), source.receivedCount(), source.retainedCount(), source.truncated());
    }
}
