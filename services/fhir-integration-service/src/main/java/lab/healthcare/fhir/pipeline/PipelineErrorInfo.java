package lab.healthcare.fhir.pipeline;

/**
 * Sanitized failure description. Never includes tokens, secrets, Patient IDs,
 * or FHIR JSON.
 */
public record PipelineErrorInfo(
        String code, String category, boolean retryable, String safeMessage, Integer providerStatus) {

    public PipelineErrorInfo {
        if (code == null || code.isBlank()) {
            throw new IllegalArgumentException("Pipeline error code must be provided");
        }
        code = code.trim();
        category = category == null ? "" : category.trim();
        safeMessage = SafePipelineLog.sanitize(safeMessage == null ? "" : safeMessage.trim());
    }

    @Override
    public String toString() {
        return "PipelineErrorInfo[code="
                + code
                + ", category="
                + category
                + ", retryable="
                + retryable
                + ", providerStatus="
                + (providerStatus == null ? "" : providerStatus)
                + "]";
    }
}
