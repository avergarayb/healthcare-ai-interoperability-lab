package lab.healthcare.fhir.resilience;

import lab.healthcare.fhir.exception.FhirClientException;
import lab.healthcare.fhir.exception.FhirErrorCategory;
import lab.healthcare.fhir.exception.FhirErrorClassifier;

import java.time.Clock;
import java.time.Instant;

/**
 * Per-destination state machine. Evaluates the terminal logical outcome, not
 * each retry attempt. Time is injected so tests can advance the reset timeout.
 */
public class FhirCircuitBreaker {

    private final String destination;
    private final FhirCircuitBreakerPolicy policy;
    private final Clock clock;

    private CircuitBreakerState state = CircuitBreakerState.CLOSED;
    private int consecutiveFailures;
    private Instant openedAt;
    private boolean probeInFlight;

    public FhirCircuitBreaker(String destination, FhirCircuitBreakerPolicy policy, Clock clock) {
        if (destination == null || destination.isBlank()) {
            throw new IllegalArgumentException("Circuit destination must be provided");
        }
        if (policy == null) {
            throw new IllegalArgumentException("Circuit breaker policy must be provided");
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

    public FhirCircuitBreakerPolicy policy() {
        return policy;
    }

    public synchronized CircuitBreakerState state() {
        transitionIfResetElapsed();
        return state;
    }

    public synchronized int consecutiveFailures() {
        return consecutiveFailures;
    }

    public synchronized void acquire() {
        transitionIfResetElapsed();
        switch (state) {
            case CLOSED -> {
            }
            case HALF_OPEN -> {
                if (probeInFlight) {
                    throw new CircuitBreakerOpenException(destination);
                }
                probeInFlight = true;
            }
            case OPEN -> throw new CircuitBreakerOpenException(destination);
        }
    }

    public synchronized void recordSuccess() {
        consecutiveFailures = 0;
        openedAt = null;
        probeInFlight = false;
        state = CircuitBreakerState.CLOSED;
    }

    public synchronized void recordFailure(FhirErrorCategory category) {
        probeInFlight = false;
        if (!policy.affectsCircuit(category)) {
            if (state == CircuitBreakerState.HALF_OPEN) {
                consecutiveFailures = 0;
                openedAt = null;
                state = CircuitBreakerState.CLOSED;
            }
            return;
        }
        consecutiveFailures++;
        if (state == CircuitBreakerState.HALF_OPEN || consecutiveFailures >= policy.failureThreshold()) {
            open();
        }
    }

    public synchronized void recordFailure(RuntimeException ex) {
        recordFailure(categoryOf(ex));
    }

    static FhirErrorCategory categoryOf(RuntimeException ex) {
        if (ex instanceof CircuitBreakerOpenException open) {
            return open.category();
        }
        if (ex instanceof FhirClientException fhir) {
            return fhir.category();
        }
        return FhirErrorClassifier.classify(ex).category();
    }

    private void transitionIfResetElapsed() {
        if (state != CircuitBreakerState.OPEN || openedAt == null) {
            return;
        }
        Instant resetAt = openedAt.plus(policy.resetTimeout());
        if (!clock.instant().isBefore(resetAt)) {
            state = CircuitBreakerState.HALF_OPEN;
            probeInFlight = false;
        }
    }

    private void open() {
        state = CircuitBreakerState.OPEN;
        openedAt = clock.instant();
        probeInFlight = false;
    }
}
