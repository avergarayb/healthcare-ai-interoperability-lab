package lab.healthcare.fhir.resilience.ratelimit;

import lab.healthcare.fhir.resilience.MutableClock;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class FhirRateLimiterRegistryTest {

    @Test
    void isolatesQuotaPerDestination() {
        MutableClock clock = MutableClock.epoch();
        FhirRateLimiterRegistry registry = FhirRateLimiterRegistry.of(
                FhirRateLimiterPolicy.defaults(), clock);
        FhirRateLimiter destinationA = registry.forDestination("destination-a");
        FhirRateLimiter destinationB = registry.forDestination("destination-b");

        for (int i = 0; i < 10; i++) {
            destinationA.acquire();
        }

        assertThatThrownBy(destinationA::acquire).isInstanceOf(RateLimitExceededException.class);
        destinationB.acquire();
        assertThat(destinationB.acceptedInWindow()).isEqualTo(1);
        assertThat(registry.forDestination("destination-a")).isSameAs(destinationA);
    }
}
