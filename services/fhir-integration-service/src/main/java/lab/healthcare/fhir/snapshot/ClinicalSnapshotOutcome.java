package lab.healthcare.fhir.snapshot;

/**
 * Global diagnosis of a controlled clinical snapshot. Not a clinical payload.
 */
public enum ClinicalSnapshotOutcome {
    SNAPSHOT_COMPLETE,
    SNAPSHOT_PARTIAL,
    SNAPSHOT_UNAVAILABLE,
    PATIENT_CONTEXT_NOT_CONFIGURED,
    AUTHENTICATION_REQUIRED
}
