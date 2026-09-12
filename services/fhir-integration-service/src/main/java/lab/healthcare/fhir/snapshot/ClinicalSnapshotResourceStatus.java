package lab.healthcare.fhir.snapshot;

/**
 * Per-resource operational status. Empty HTTP 200 Bundles are {@link #SUCCESS}.
 * {@link #TIMEOUT} is a persisted operational refinement of a failed search or
 * read; it is not a new Model Boundary clinical field.
 */
public enum ClinicalSnapshotResourceStatus {
    SUCCESS,
    UNAVAILABLE,
    UNAUTHORIZED,
    TIMEOUT,
    FAILED
}
