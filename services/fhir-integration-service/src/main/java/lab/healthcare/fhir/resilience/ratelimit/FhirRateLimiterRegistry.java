package lab.healthcare.fhir.resilience.ratelimit;

import java.time.Clock;
import java.util.concurrent.ConcurrentHashMap;

/**
 * One rate limiter per destination/profile name.
 */
public class FhirRateLimiterRegistry {

    private final FhirRateLimiterPolicy policy;
    private final Clock clock;
    private final ConcurrentHashMap<String, FhirRateLimiter> limiters = new ConcurrentHashMap<>();

    public FhirRateLimiterRegistry() {
        this(FhirRateLimiterPolicy.defaults(), Clock.systemUTC());
    }

    public static FhirRateLimiterRegistry of(FhirRateLimiterPolicy policy, Clock clock) {
        return new FhirRateLimiterRegistry(policy, clock);
    }

    FhirRateLimiterRegistry(FhirRateLimiterPolicy policy, Clock clock) {
        if (policy == null) {
            throw new IllegalArgumentException("Rate limiter policy must be provided");
        }
        if (clock == null) {
            throw new IllegalArgumentException("Clock must be provided");
        }
        this.policy = policy;
        this.clock = clock;
    }

    public FhirRateLimiterPolicy policy() {
        return policy;
    }

    public FhirRateLimiter forDestination(String destination) {
        if (destination == null || destination.isBlank()) {
            throw new IllegalArgumentException("Rate limiter destination must be provided");
        }
        return limiters.computeIfAbsent(destination, name -> new FhirRateLimiter(name, policy, clock));
    }
}
