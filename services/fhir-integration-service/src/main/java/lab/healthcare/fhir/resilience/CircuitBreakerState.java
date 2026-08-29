package lab.healthcare.fhir.resilience;

/**
 * Three-state circuit breaker model. Transitions are owned by {@link FhirCircuitBreaker}.
 */
public enum CircuitBreakerState {
    CLOSED,
    OPEN,
    HALF_OPEN
}
