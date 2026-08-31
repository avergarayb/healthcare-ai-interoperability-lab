package lab.healthcare.fhir.resilience;

import lab.healthcare.fhir.resilience.bulkhead.FhirBulkheadRegistry;
import lab.healthcare.fhir.resilience.ratelimit.FhirRateLimiterRegistry;

import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.time.Clock;

/**
 * Wires YAML policy sizes into the existing retry, circuit, rate-limit and
 * bulkhead components. Does not change eligibility rules or FhirService.
 */
@Configuration
@EnableConfigurationProperties(FhirResilienceProperties.class)
public class FhirResilienceConfiguration {

    @Bean
    public FhirRetryExecutor fhirRetryExecutor(FhirResilienceProperties properties) {
        return FhirRetryExecutor.of(properties.retryPolicy(), FhirSleeper.threadSleep());
    }

    @Bean
    public FhirCircuitBreakerRegistry fhirCircuitBreakerRegistry(FhirResilienceProperties properties) {
        return FhirCircuitBreakerRegistry.of(properties.circuitBreakerPolicy(), Clock.systemUTC());
    }

    @Bean
    public FhirRateLimiterRegistry fhirRateLimiterRegistry(FhirResilienceProperties properties) {
        return FhirRateLimiterRegistry.of(properties.rateLimiterPolicy(), Clock.systemUTC());
    }

    @Bean
    public FhirBulkheadRegistry fhirBulkheadRegistry(FhirResilienceProperties properties) {
        return FhirBulkheadRegistry.of(properties.bulkheadPolicy());
    }
}
