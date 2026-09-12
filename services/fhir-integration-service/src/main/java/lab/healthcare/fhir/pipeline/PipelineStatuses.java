package lab.healthcare.fhir.pipeline;

import lab.healthcare.fhir.exception.FhirErrorCategory;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotOutcome;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotResourceStatus;

/**
 * Maps existing snapshot/projection statuses onto pipeline statuses. Does not
 * switch on vendor.
 */
public final class PipelineStatuses {

    private PipelineStatuses() {
    }

    public static PipelineStageStatus ofResource(ClinicalSnapshotResourceStatus status) {
        if (status == null) {
            return PipelineStageStatus.NOT_REQUESTED;
        }
        return switch (status) {
            case SUCCESS -> PipelineStageStatus.SUCCESS;
            case UNAVAILABLE -> PipelineStageStatus.NOT_AVAILABLE;
            case UNAUTHORIZED -> PipelineStageStatus.AUTHENTICATION_FAILED;
            case TIMEOUT -> PipelineStageStatus.TIMEOUT;
            case FAILED -> PipelineStageStatus.PROVIDER_ERROR;
        };
    }

    public static PipelineStageStatus ofOutcome(ClinicalSnapshotOutcome outcome) {
        if (outcome == null) {
            return PipelineStageStatus.FAILED;
        }
        return switch (outcome) {
            case SNAPSHOT_COMPLETE -> PipelineStageStatus.SUCCESS;
            case SNAPSHOT_PARTIAL -> PipelineStageStatus.PARTIAL;
            case AUTHENTICATION_REQUIRED -> PipelineStageStatus.AUTHENTICATION_FAILED;
            case PATIENT_CONTEXT_NOT_CONFIGURED -> PipelineStageStatus.VALIDATION_FAILED;
            case SNAPSHOT_UNAVAILABLE -> PipelineStageStatus.FAILED;
        };
    }

    public static PipelineErrorInfo errorFor(ClinicalSnapshotResourceStatus status) {
        if (status == null || status == ClinicalSnapshotResourceStatus.SUCCESS) {
            return null;
        }
        return switch (status) {
            case UNAVAILABLE -> new PipelineErrorInfo(
                    PipelineErrorCodes.FHIR_NOT_AVAILABLE,
                    FhirErrorCategory.NOT_FOUND.name(),
                    false,
                    "Resource search is not available",
                    null);
            case UNAUTHORIZED -> new PipelineErrorInfo(
                    PipelineErrorCodes.FHIR_AUTHENTICATION_FAILED,
                    FhirErrorCategory.AUTHORIZATION_ERROR.name(),
                    false,
                    FhirErrorCategory.AUTHORIZATION_ERROR.safeMessage(),
                    403);
            case TIMEOUT -> new PipelineErrorInfo(
                    PipelineErrorCodes.FHIR_TIMEOUT,
                    FhirErrorCategory.TIMEOUT.name(),
                    true,
                    FhirErrorCategory.TIMEOUT.safeMessage(),
                    null);
            case FAILED -> new PipelineErrorInfo(
                    PipelineErrorCodes.FHIR_PROVIDER_ERROR,
                    FhirErrorCategory.UNKNOWN.name(),
                    false,
                    FhirErrorCategory.UNKNOWN.safeMessage(),
                    null);
            case SUCCESS -> null;
        };
    }
}
