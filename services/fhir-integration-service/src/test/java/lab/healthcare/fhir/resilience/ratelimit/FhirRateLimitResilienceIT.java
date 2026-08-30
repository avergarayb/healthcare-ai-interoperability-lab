package lab.healthcare.fhir.resilience.ratelimit;

import lab.healthcare.fhir.client.FhirService;
import lab.healthcare.fhir.client.SyntheticPatients;
import lab.healthcare.fhir.exception.FhirErrorCategory;
import lab.healthcare.fhir.resilience.CircuitBreakerState;
import lab.healthcare.fhir.resilience.FhirCircuitBreaker;
import lab.healthcare.fhir.resilience.FhirCircuitBreakerPolicy;
import lab.healthcare.fhir.resilience.FhirCircuitBreakerRegistry;
import lab.healthcare.fhir.resilience.MutableClock;
import lab.healthcare.fhir.routing.RoutingRequest;
import lab.healthcare.fhir.routing.RoutingService;

import ca.uhn.fhir.rest.client.api.IGenericClient;
import org.hl7.fhir.r4.model.Patient;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestInstance;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import java.time.Duration;
import java.util.concurrent.atomic.AtomicInteger;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE)
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
class FhirRateLimitResilienceIT {

    @Autowired
    private RoutingService routingService;

    @Autowired
    private FhirRateLimiterRegistry rateLimiters;

    @Autowired
    private FhirCircuitBreakerRegistry circuitBreakers;

    @Autowired
    private IGenericClient fhirClient;

    @BeforeAll
    void seedSyntheticPatients() {
        SyntheticPatients.seed(fhirClient);
    }

    @Test
    void healthyLocalHapiReadIsAdmitted() {
        Patient patient = routingService.readPatient(
                RoutingRequest.readPatient("local-hapi", "patient-001", "rl-healthy"));

        assertThat(patient.getIdElement().getIdPart()).isEqualTo("patient-001");
        assertThat(rateLimiters.policy().maxOperations()).isEqualTo(10);
        assertThat(rateLimiters.policy().window()).isEqualTo(Duration.ofSeconds(1));
        assertThat(circuitBreakers.forDestination("local-hapi").state()).isEqualTo(CircuitBreakerState.CLOSED);
        assertThat(new FhirService(fhirClient).readPatient("patient-001").getIdElement().getIdPart())
                .isEqualTo("patient-001");
    }

    @Test
    void syntheticLimitBlocksBeforeFhirAndDoesNotOpenTheCircuit() {
        MutableClock clock = MutableClock.epoch();
        FhirRateLimiter limiter = new FhirRateLimiter(
                "synthetic-busy", FhirRateLimiterPolicy.defaults(), clock);
        FhirCircuitBreaker breaker = new FhirCircuitBreaker(
                "synthetic-busy", FhirCircuitBreakerPolicy.defaults(), clock);
        AtomicInteger fhirCalls = new AtomicInteger();

        for (int i = 0; i < 10; i++) {
            limiter.acquire();
            fhirCalls.incrementAndGet();
        }
        assertThatThrownBy(limiter::acquire).isInstanceOf(RateLimitExceededException.class);
        breaker.recordFailure(FhirErrorCategory.RATE_LIMITED);

        assertThat(fhirCalls.get()).isEqualTo(10);
        assertThat(breaker.state()).isEqualTo(CircuitBreakerState.CLOSED);
        assertThat(breaker.consecutiveFailures()).isZero();
        clock.advance(Duration.ofSeconds(1));
        limiter.acquire();
        assertThat(limiter.acceptedInWindow()).isEqualTo(1);
        assertThat(FhirErrorCategory.RATE_LIMITED.safeMessage()).doesNotContain("access_token");
    }
}
