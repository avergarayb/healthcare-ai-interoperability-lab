package lab.healthcare.fhir.resilience;

import lab.healthcare.fhir.resilience.bulkhead.FhirBulkheadRegistry;
import lab.healthcare.fhir.resilience.ratelimit.FhirRateLimiterRegistry;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;

import java.time.Duration;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE)
class FhirResilienceConfigurationTest {

    @Autowired
    private FhirResilienceProperties properties;

    @Autowired
    private FhirRetryExecutor retryExecutor;

    @Autowired
    private FhirCircuitBreakerRegistry circuitBreakers;

    @Autowired
    private FhirRateLimiterRegistry rateLimiters;

    @Autowired
    private FhirBulkheadRegistry bulkheads;

    @Test
    void applicationYamlBindsAndWiresPipelineBeans() {
        assertThat(properties.rateLimit().maxOperations()).isEqualTo(10);
        assertThat(properties.rateLimit().window()).isEqualTo(Duration.ofSeconds(1));
        assertThat(properties.bulkhead().maxConcurrentOperations()).isEqualTo(5);
        assertThat(properties.circuitBreaker().failureThreshold()).isEqualTo(3);
        assertThat(properties.circuitBreaker().resetTimeout()).isEqualTo(Duration.ofSeconds(30));
        assertThat(properties.retry().maxAttempts()).isEqualTo(3);
        assertThat(properties.retry().initialBackoff()).isEqualTo(Duration.ofMillis(100));
        assertThat(retryExecutor.policy().maxAttempts()).isEqualTo(3);
        assertThat(retryExecutor.policy().initialDelayMs()).isEqualTo(100L);
        assertThat(circuitBreakers.policy().failureThreshold()).isEqualTo(3);
        assertThat(rateLimiters.policy().maxOperations()).isEqualTo(10);
        assertThat(bulkheads.policy().maxConcurrentOperations()).isEqualTo(5);
        assertThat(properties.retryPolicy().isRetryable(lab.healthcare.fhir.exception.FhirErrorCategory.RATE_LIMITED))
                .isFalse();
    }

    @Test
    void invalidYamlFailsStartup() {
        new ApplicationContextRunner()
                .withUserConfiguration(FhirResilienceConfiguration.class)
                .withPropertyValues(
                        "fhir.resilience.rate-limit.max-operations=10",
                        "fhir.resilience.rate-limit.window=1s",
                        "fhir.resilience.bulkhead.max-concurrent-operations=5",
                        "fhir.resilience.circuit-breaker.failure-threshold=3",
                        "fhir.resilience.circuit-breaker.reset-timeout=30s",
                        "fhir.resilience.retry.max-attempts=0",
                        "fhir.resilience.retry.initial-backoff=100ms")
                .run(context -> assertThat(context).hasFailed());
    }
}
