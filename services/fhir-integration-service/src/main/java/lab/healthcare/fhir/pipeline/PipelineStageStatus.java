package lab.healthcare.fhir.pipeline;

/**
 * Normalized technical status for one pipeline stage or the aggregate run.
 * Not a clinical availability verdict and not a model-boundary field.
 */
public enum PipelineStageStatus {
    SUCCESS,
    PARTIAL,
    FAILED,
    NOT_REQUESTED,
    NOT_AVAILABLE,
    TIMEOUT,
    AUTHENTICATION_FAILED,
    PROVIDER_ERROR,
    VALIDATION_FAILED,
    REJECTED
}
