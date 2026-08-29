package lab.healthcare.fhir.resilience;

import lab.healthcare.fhir.exception.FhirErrorCategory;

/**
 * Bounded retry policy keyed off Task 023 categories. Only transient
 * categories retry. maxAttempts is total executions, not extra retries.
 */
public record FhirRetryPolicy(int maxAttempts, long initialDelayMs) {

    public static final int DEFAULT_MAX_ATTEMPTS = 3;
    public static final long DEFAULT_INITIAL_DELAY_MS = 100L;

    public FhirRetryPolicy {
        if (maxAttempts < 1) {
            throw new IllegalArgumentException("maxAttempts must be at least 1");
        }
        if (initialDelayMs < 0) {
            throw new IllegalArgumentException("initialDelayMs must be zero or positive");
        }
    }

    public static FhirRetryPolicy defaults() {
        return new FhirRetryPolicy(DEFAULT_MAX_ATTEMPTS, DEFAULT_INITIAL_DELAY_MS);
    }

    public boolean isRetryable(FhirErrorCategory category) {
        return category == FhirErrorCategory.SERVER_ERROR
                || category == FhirErrorCategory.TIMEOUT
                || category == FhirErrorCategory.CONNECTION_ERROR;
    }

    /**
     * Delay before a 1-based attempt. Attempt 1 is immediate.
     * Attempt n (n&gt;1) waits {@code initialDelay × 2^(n-2)}.
     */
    public long delayBeforeAttempt(int attempt) {
        if (attempt <= 1) {
            return 0L;
        }
        int retryNumber = attempt - 1;
        return initialDelayMs * (1L << (retryNumber - 1));
    }

    public FhirRetryDecision decide(FhirErrorCategory category, int failedAttempt) {
        if (category == null || failedAttempt < 1) {
            return FhirRetryDecision.stop();
        }
        if (!isRetryable(category) || failedAttempt >= maxAttempts) {
            return FhirRetryDecision.stop();
        }
        return new FhirRetryDecision(true, delayBeforeAttempt(failedAttempt + 1));
    }
}
