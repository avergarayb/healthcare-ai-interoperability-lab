package lab.healthcare.fhir.modelboundary;

import lab.healthcare.fhir.snapshot.ClinicalSnapshotOutcome;

/**
 * HTTP mapping for the consumer surface. Matches the laboratory pages.
 */
public final class ModelBoundaryHttpStatuses {

    private ModelBoundaryHttpStatuses() {
    }

    public static int of(ClinicalSnapshotOutcome outcome) {
        if (outcome == null) {
            throw new IllegalArgumentException("Model boundary outcome must be provided");
        }
        return switch (outcome) {
            case SNAPSHOT_COMPLETE, SNAPSHOT_PARTIAL -> 200;
            case AUTHENTICATION_REQUIRED -> 401;
            case PATIENT_CONTEXT_NOT_CONFIGURED -> 409;
            case SNAPSHOT_UNAVAILABLE -> 502;
        };
    }
}
