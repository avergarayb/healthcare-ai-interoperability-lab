package lab.healthcare.fhir.resilience;

import java.time.Clock;
import java.util.concurrent.ConcurrentHashMap;

/**
 * One breaker per destination/profile name. A failing server must not open
 * another destination's circuit.
 */
public class FhirCircuitBreakerRegistry {

    private final FhirCircuitBreakerPolicy policy;
    private final Clock clock;
    private final ConcurrentHashMap<String, FhirCircuitBreaker> breakers = new ConcurrentHashMap<>();

    public FhirCircuitBreakerRegistry() {
        this(FhirCircuitBreakerPolicy.defaults(), Clock.systemUTC());
    }

    public static FhirCircuitBreakerRegistry of(FhirCircuitBreakerPolicy policy, Clock clock) {
        return new FhirCircuitBreakerRegistry(policy, clock);
    }

    FhirCircuitBreakerRegistry(FhirCircuitBreakerPolicy policy, Clock clock) {
        if (policy == null) {
            throw new IllegalArgumentException("Circuit breaker policy must be provided");
        }
        if (clock == null) {
            throw new IllegalArgumentException("Clock must be provided");
        }
        this.policy = policy;
        this.clock = clock;
    }

    public FhirCircuitBreakerPolicy policy() {
        return policy;
    }

    public FhirCircuitBreaker forDestination(String destination) {
        if (destination == null || destination.isBlank()) {
            throw new IllegalArgumentException("Circuit destination must be provided");
        }
        return breakers.computeIfAbsent(destination, name -> new FhirCircuitBreaker(name, policy, clock));
    }
}
