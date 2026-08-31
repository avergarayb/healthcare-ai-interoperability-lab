package lab.healthcare.fhir.resilience;

import org.junit.jupiter.api.Test;

import java.time.Duration;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class FhirResiliencePropertiesTest {

    @Test
    void defaultsMatchLaboratoryYaml() {
        FhirResilienceProperties properties = FhirResilienceProperties.defaults();

        assertThat(properties.rateLimit().maxOperations()).isEqualTo(10);
        assertThat(properties.rateLimit().window()).isEqualTo(Duration.ofSeconds(1));
        assertThat(properties.bulkhead().maxConcurrentOperations()).isEqualTo(5);
        assertThat(properties.circuitBreaker().failureThreshold()).isEqualTo(3);
        assertThat(properties.circuitBreaker().resetTimeout()).isEqualTo(Duration.ofSeconds(30));
        assertThat(properties.retry().maxAttempts()).isEqualTo(3);
        assertThat(properties.retry().initialBackoff()).isEqualTo(Duration.ofMillis(100));
        assertThat(properties.retryPolicy().initialDelayMs()).isEqualTo(100L);
        assertThat(properties.retryPolicy().isRetryable(lab.healthcare.fhir.exception.FhirErrorCategory.TIMEOUT))
                .isTrue();
        assertThat(properties.retryPolicy().isRetryable(lab.healthcare.fhir.exception.FhirErrorCategory.NOT_FOUND))
                .isFalse();
    }

    @Test
    void invalidValuesFailFast() {
        FhirResilienceProperties valid = FhirResilienceProperties.defaults();
        assertThatThrownBy(() -> new FhirResilienceProperties.RateLimit(0, Duration.ofSeconds(1)))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("max-operations");
        assertThatThrownBy(() -> new FhirResilienceProperties.RateLimit(10, Duration.ZERO))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("window");
        assertThatThrownBy(() -> new FhirResilienceProperties.Bulkhead(0))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("max-concurrent-operations");
        assertThatThrownBy(() -> new FhirResilienceProperties.CircuitBreaker(0, Duration.ofSeconds(30)))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("failure-threshold");
        assertThatThrownBy(() -> new FhirResilienceProperties.CircuitBreaker(3, Duration.ofSeconds(-1)))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("reset-timeout");
        assertThatThrownBy(() -> new FhirResilienceProperties.Retry(0, Duration.ofMillis(100)))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("max-attempts");
        assertThatThrownBy(() -> new FhirResilienceProperties.Retry(3, Duration.ofMillis(-1)))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("initial-backoff");
        assertThatThrownBy(() -> new FhirResilienceProperties(null, valid.bulkhead(), valid.circuitBreaker(), valid.retry()))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("rate-limit");
    }
}
