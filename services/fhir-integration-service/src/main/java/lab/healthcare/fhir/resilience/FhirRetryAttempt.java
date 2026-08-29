package lab.healthcare.fhir.resilience;

/**
 * One execution of a retried operation. Used for audit, not for FHIR payloads.
 */
public record FhirRetryAttempt(
        int attempt,
        int maxAttempts,
        boolean success,
        boolean willRetry,
        long delayMs,
        long durationMs,
        RuntimeException error) {

    public FhirRetryAttempt {
        if (attempt < 1) {
            throw new IllegalArgumentException("attempt must be at least 1");
        }
        if (maxAttempts < 1) {
            throw new IllegalArgumentException("maxAttempts must be at least 1");
        }
        if (delayMs < 0 || durationMs < 0) {
            throw new IllegalArgumentException("durations must be zero or positive");
        }
        if (success) {
            willRetry = false;
            delayMs = 0L;
            error = null;
        } else if (error == null) {
            throw new IllegalArgumentException("Failed attempt must include the exception");
        }
        if (!willRetry) {
            delayMs = 0L;
        }
    }
}
