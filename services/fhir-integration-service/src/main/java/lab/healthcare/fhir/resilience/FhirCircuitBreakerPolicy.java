package lab.healthcare.fhir.resilience;

import lab.healthcare.fhir.exception.FhirErrorCategory;

import java.time.Duration;

/**
 * Circuit policy. Counts failed logical operations, not retry attempts.
 */
public record FhirCircuitBreakerPolicy(int failureThreshold, Duration resetTimeout) {

    public static final int DEFAULT_FAILURE_THRESHOLD = 3;
    public static final Duration DEFAULT_RESET_TIMEOUT = Duration.ofSeconds(30);

    public FhirCircuitBreakerPolicy {
        if (failureThreshold < 1) {
            throw new IllegalArgumentException("failureThreshold must be at least 1");
        }
        if (resetTimeout == null || resetTimeout.isZero() || resetTimeout.isNegative()) {
            throw new IllegalArgumentException("resetTimeout must be positive");
        }
    }

    public static FhirCircuitBreakerPolicy defaults() {
        return new FhirCircuitBreakerPolicy(DEFAULT_FAILURE_THRESHOLD, DEFAULT_RESET_TIMEOUT);
    }

    public boolean affectsCircuit(FhirErrorCategory category) {
        return category == FhirErrorCategory.SERVER_ERROR
                || category == FhirErrorCategory.TIMEOUT
                || category == FhirErrorCategory.CONNECTION_ERROR;
    }
}
