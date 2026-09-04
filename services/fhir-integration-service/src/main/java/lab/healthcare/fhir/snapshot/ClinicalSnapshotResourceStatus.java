package lab.healthcare.fhir.snapshot;

/**
 * Per-resource operational status. Empty HTTP 200 Bundles are {@link #SUCCESS}.
 */
public enum ClinicalSnapshotResourceStatus {
    SUCCESS,
    UNAVAILABLE,
    UNAUTHORIZED,
    FAILED
}
