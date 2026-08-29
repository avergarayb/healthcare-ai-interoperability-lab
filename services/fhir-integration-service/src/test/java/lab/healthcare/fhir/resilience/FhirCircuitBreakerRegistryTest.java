package lab.healthcare.fhir.resilience;

import lab.healthcare.fhir.exception.FhirErrorCategory;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class FhirCircuitBreakerRegistryTest {

    @Test
    void isolatesCircuitStatePerDestination() {
        MutableClock clock = MutableClock.epoch();
        FhirCircuitBreakerRegistry registry = FhirCircuitBreakerRegistry.of(
                FhirCircuitBreakerPolicy.defaults(), clock);
        FhirCircuitBreaker destinationA = registry.forDestination("destination-a");
        FhirCircuitBreaker destinationB = registry.forDestination("destination-b");

        failOpen(destinationA);

        assertThat(destinationA.state()).isEqualTo(CircuitBreakerState.OPEN);
        assertThat(destinationB.state()).isEqualTo(CircuitBreakerState.CLOSED);
        assertThat(registry.forDestination("destination-a")).isSameAs(destinationA);
        destinationB.acquire();
        destinationB.recordSuccess();
        assertThat(destinationB.state()).isEqualTo(CircuitBreakerState.CLOSED);
    }

    private static void failOpen(FhirCircuitBreaker breaker) {
        for (int i = 0; i < 3; i++) {
            breaker.acquire();
            breaker.recordFailure(FhirErrorCategory.CONNECTION_ERROR);
        }
    }
}
