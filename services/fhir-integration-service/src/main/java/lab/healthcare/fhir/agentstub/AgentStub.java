package lab.healthcare.fhir.agentstub;

import lab.healthcare.fhir.modelboundary.BoundaryCollection;
import lab.healthcare.fhir.modelboundary.ModelBoundaryContract;
import lab.healthcare.fhir.modelboundary.ModelBoundaryContractVersion;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotOutcome;
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
        if (!ModelBoundaryContractVersion.V1.equals(contract.contractVersion())) {
            throw new IllegalArgumentException("Agent stub accepts only model boundary contract v1");
        }
        requireExpectedSections(contract);
        ObservedCollection conditions = collection(contract.conditions());
        ObservedCollection observations = collection(contract.observations());
        ObservedCollection diagnosticReports = collection(contract.diagnosticReports());
        ObservedCollection medicationRequests = collection(contract.medicationRequests());
        return new AgentStubObservation(
                contract.contractVersion(),
                contract.destination(),
                contract.contextSource(),
                contract.outcome(),
                contract.patient() == null ? null : contract.patient().status(),
                conditions,
                observations,
                diagnosticReports,
                medicationRequests,
                hasClinicalData(conditions, observations, diagnosticReports, medicationRequests),
                true,
                false);
    }

    private static void requireExpectedSections(ModelBoundaryContract contract) {
        ClinicalSnapshotOutcome outcome = contract.outcome();
        if (outcome != ClinicalSnapshotOutcome.SNAPSHOT_COMPLETE
                && outcome != ClinicalSnapshotOutcome.SNAPSHOT_PARTIAL) {
            return;
        }
        if (contract.patient() == null
                || contract.conditions() == null
                || contract.observations() == null
                || contract.diagnosticReports() == null) {
            throw new IllegalArgumentException("Complete or partial v1 contracts require patient and included collections");
        }
    }

    private static boolean hasClinicalData(
            ObservedCollection conditions,
            ObservedCollection observations,
            ObservedCollection diagnosticReports,
            ObservedCollection medicationRequests) {
        return retainedPositive(conditions)
                || retainedPositive(observations)
                || retainedPositive(diagnosticReports)
                || retainedPositive(medicationRequests);
    }

    private static boolean retainedPositive(ObservedCollection collection) {
        return collection != null && collection.retainedCount() != null && collection.retainedCount() > 0;
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
