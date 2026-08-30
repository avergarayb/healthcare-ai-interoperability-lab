package lab.healthcare.fhir.resilience.ratelimit;

import java.time.Duration;

/**
 * Fixed-window admission quota. Counts accepted logical operations, not retries.
 */
public record FhirRateLimiterPolicy(int maxOperations, Duration window) {

    public static final int DEFAULT_MAX_OPERATIONS = 10;
    public static final Duration DEFAULT_WINDOW = Duration.ofSeconds(1);

    public FhirRateLimiterPolicy {
        if (maxOperations < 1) {
            throw new IllegalArgumentException("maxOperations must be at least 1");
        }
        if (window == null || window.isZero() || window.isNegative()) {
            throw new IllegalArgumentException("window must be positive");
        }
    }

    public static FhirRateLimiterPolicy defaults() {
        return new FhirRateLimiterPolicy(DEFAULT_MAX_OPERATIONS, DEFAULT_WINDOW);
    }
}
