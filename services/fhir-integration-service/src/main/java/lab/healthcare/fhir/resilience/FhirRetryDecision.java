package lab.healthcare.fhir.resilience;

/**
 * Outcome of a retry policy check after one failed attempt.
 */
public record FhirRetryDecision(boolean retry, long delayMs) {

    public FhirRetryDecision {
        if (delayMs < 0) {
            throw new IllegalArgumentException("Retry delay must be zero or positive");
        }
        if (!retry) {
            delayMs = 0L;
        }
    }

    public static FhirRetryDecision stop() {
        return new FhirRetryDecision(false, 0L);
    }
}
