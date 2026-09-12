package lab.healthcare.fhir.pipeline;

/**
 * One pipeline stage. Counts are operational; values are never included.
 */
public record PipelineStageDiagnosis(
        String stage,
        PipelineStageStatus status,
        boolean critical,
        PipelineErrorInfo error,
        Integer receivedCount,
        Integer retainedCount,
        Boolean truncated,
        Long durationMs) {

    public PipelineStageDiagnosis {
        if (stage == null || stage.isBlank()) {
            throw new IllegalArgumentException("Pipeline stage must be provided");
        }
        if (status == null) {
            throw new IllegalArgumentException("Pipeline stage status must be provided");
        }
        stage = stage.trim();
    }

    public static PipelineStageDiagnosis of(String stage, PipelineStageStatus status, boolean critical) {
        return new PipelineStageDiagnosis(stage, status, critical, null, null, null, null, null);
    }

    public static PipelineStageDiagnosis collection(
            String stage,
            PipelineStageStatus status,
            Integer receivedCount,
            Integer retainedCount,
            Boolean truncated,
            PipelineErrorInfo error) {
        return new PipelineStageDiagnosis(
                stage, status, false, error, receivedCount, retainedCount, truncated, null);
    }

    @Override
    public String toString() {
        return "PipelineStageDiagnosis[stage="
                + stage
                + ", status="
                + status
                + ", critical="
                + critical
                + ", receivedCount="
                + receivedCount
                + ", retainedCount="
                + retainedCount
                + ", truncated="
                + truncated
                + "]";
    }
}
