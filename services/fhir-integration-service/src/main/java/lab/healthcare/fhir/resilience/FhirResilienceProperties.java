package lab.healthcare.fhir.resilience;

import lab.healthcare.fhir.resilience.bulkhead.FhirBulkheadPolicy;
import lab.healthcare.fhir.resilience.ratelimit.FhirRateLimiterPolicy;

import org.springframework.boot.context.properties.ConfigurationProperties;

import java.time.Duration;

/**
 * Bound {@code fhir.resilience} policy sizes. Eligibility (which categories
 * retry or open a circuit) stays on the existing policy objects.
 */
@ConfigurationProperties(prefix = "fhir.resilience")
public record FhirResilienceProperties(
        RateLimit rateLimit,
        Bulkhead bulkhead,
        CircuitBreaker circuitBreaker,
        Retry retry) {

    public FhirResilienceProperties {
        if (rateLimit == null) {
            throw new IllegalArgumentException("fhir.resilience.rate-limit must be provided");
        }
        if (bulkhead == null) {
            throw new IllegalArgumentException("fhir.resilience.bulkhead must be provided");
        }
        if (circuitBreaker == null) {
            throw new IllegalArgumentException("fhir.resilience.circuit-breaker must be provided");
        }
        if (retry == null) {
            throw new IllegalArgumentException("fhir.resilience.retry must be provided");
        }
    }

    public static FhirResilienceProperties defaults() {
        return new FhirResilienceProperties(
                new RateLimit(FhirRateLimiterPolicy.DEFAULT_MAX_OPERATIONS, FhirRateLimiterPolicy.DEFAULT_WINDOW),
                new Bulkhead(FhirBulkheadPolicy.DEFAULT_MAX_CONCURRENT_OPERATIONS),
                new CircuitBreaker(
                        FhirCircuitBreakerPolicy.DEFAULT_FAILURE_THRESHOLD,
                        FhirCircuitBreakerPolicy.DEFAULT_RESET_TIMEOUT),
                new Retry(
                        FhirRetryPolicy.DEFAULT_MAX_ATTEMPTS,
                        Duration.ofMillis(FhirRetryPolicy.DEFAULT_INITIAL_DELAY_MS)));
    }

    public FhirRateLimiterPolicy rateLimiterPolicy() {
        return new FhirRateLimiterPolicy(rateLimit.maxOperations(), rateLimit.window());
    }

    public FhirBulkheadPolicy bulkheadPolicy() {
        return new FhirBulkheadPolicy(bulkhead.maxConcurrentOperations());
    }

    public FhirCircuitBreakerPolicy circuitBreakerPolicy() {
        return new FhirCircuitBreakerPolicy(circuitBreaker.failureThreshold(), circuitBreaker.resetTimeout());
    }

    public FhirRetryPolicy retryPolicy() {
        return new FhirRetryPolicy(retry.maxAttempts(), retry.initialBackoff().toMillis());
    }

    public record RateLimit(int maxOperations, Duration window) {
        public RateLimit {
            if (maxOperations < 1) {
                throw new IllegalArgumentException("max-operations must be at least 1");
            }
            if (window == null || window.isZero() || window.isNegative()) {
                throw new IllegalArgumentException("window must be positive");
            }
        }
    }

    public record Bulkhead(int maxConcurrentOperations) {
        public Bulkhead {
            if (maxConcurrentOperations < 1) {
                throw new IllegalArgumentException("max-concurrent-operations must be at least 1");
            }
        }
    }

    public record CircuitBreaker(int failureThreshold, Duration resetTimeout) {
        public CircuitBreaker {
            if (failureThreshold < 1) {
                throw new IllegalArgumentException("failure-threshold must be at least 1");
            }
            if (resetTimeout == null || resetTimeout.isZero() || resetTimeout.isNegative()) {
                throw new IllegalArgumentException("reset-timeout must be positive");
            }
        }
    }

    public record Retry(int maxAttempts, Duration initialBackoff) {
        public Retry {
            if (maxAttempts < 1) {
                throw new IllegalArgumentException("max-attempts must be at least 1");
            }
            if (initialBackoff == null || initialBackoff.isNegative()) {
                throw new IllegalArgumentException("initial-backoff must be zero or positive");
            }
        }
    }
}
