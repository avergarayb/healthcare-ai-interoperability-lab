package lab.healthcare.fhir.resilience.ratelimit;

import java.time.Clock;
import java.time.Instant;

/**
 * Per-destination fixed-window limiter. The counter increments when a logical
 * operation is accepted, before Bulkhead, Circuit Breaker, Retry, or FHIR.
 */
public class FhirRateLimiter {

    private final String destination;
    private final FhirRateLimiterPolicy policy;
    private final Clock clock;

    private Instant windowStart;
    private int accepted;

    public FhirRateLimiter(String destination, FhirRateLimiterPolicy policy, Clock clock) {
        if (destination == null || destination.isBlank()) {
            throw new IllegalArgumentException("Rate limiter destination must be provided");
        }
        if (policy == null) {
            throw new IllegalArgumentException("Rate limiter policy must be provided");
        }
        if (clock == null) {
            throw new IllegalArgumentException("Clock must be provided");
        }
        this.destination = destination;
        this.policy = policy;
        this.clock = clock;
    }

    public String destination() {
        return destination;
    }

    public FhirRateLimiterPolicy policy() {
        return policy;
    }

    public synchronized int acceptedInWindow() {
        rollWindow(clock.instant());
        return accepted;
    }

    public synchronized void acquire() {
        Instant now = clock.instant();
        rollWindow(now);
        if (accepted >= policy.maxOperations()) {
            throw new RateLimitExceededException(destination);
        }
        accepted++;
    }

    private void rollWindow(Instant now) {
        if (windowStart == null || !now.isBefore(windowStart.plus(policy.window()))) {
            windowStart = now;
            accepted = 0;
        }
    }
}
