package lab.healthcare.fhir.agentstub;

import lab.healthcare.fhir.snapshot.ClinicalSnapshotResourceStatus;

/**
 * Operational collection view. Never includes retained record values.
 */
public record ObservedCollection(
        ClinicalSnapshotResourceStatus status,
        Integer receivedCount,
        Integer retainedCount,
        Boolean truncated) {
}
