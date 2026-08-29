package lab.healthcare.fhir.resilience;

import lab.healthcare.fhir.client.FhirService;
import lab.healthcare.fhir.client.SyntheticPatients;
import lab.healthcare.fhir.exception.FhirErrorCategory;
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
class FhirCircuitBreakerResilienceIT {

    @Autowired
    private RoutingService routingService;

    @Autowired
    private FhirCircuitBreakerRegistry circuitBreakers;

    @Autowired
    private IGenericClient fhirClient;

    @BeforeAll
    void seedSyntheticPatients() {
        SyntheticPatients.seed(fhirClient);
    }

    @Test
    void healthyLocalHapiReadLeavesCircuitClosed() {
        Patient patient = routingService.readPatient(
                RoutingRequest.readPatient("local-hapi", "patient-001", "cb-healthy"));

        assertThat(patient.getIdElement().getIdPart()).isEqualTo("patient-001");
        assertThat(circuitBreakers.forDestination("local-hapi").state()).isEqualTo(CircuitBreakerState.CLOSED);
        assertThat(circuitBreakers.policy().failureThreshold()).isEqualTo(3);
        assertThat(circuitBreakers.policy().resetTimeout()).isEqualTo(Duration.ofSeconds(30));
        assertThat(new FhirService(fhirClient).readPatient("patient-001").getIdElement().getIdPart())
                .isEqualTo("patient-001");
    }

    @Test
    void syntheticFailuresOpenThenFailFastThenRecoverWithControlledTime() {
        MutableClock clock = MutableClock.epoch();
        FhirCircuitBreaker breaker = new FhirCircuitBreaker(
                "synthetic-down", FhirCircuitBreakerPolicy.defaults(), clock);
        AtomicInteger fhirCalls = new AtomicInteger();

        for (int i = 0; i < 3; i++) {
            breaker.acquire();
            fhirCalls.incrementAndGet();
            breaker.recordFailure(FhirErrorCategory.TIMEOUT);
        }
        assertThat(breaker.state()).isEqualTo(CircuitBreakerState.OPEN);

        assertThatThrownBy(breaker::acquire).isInstanceOf(CircuitBreakerOpenException.class);
        assertThat(fhirCalls.get()).isEqualTo(3);

        clock.advance(Duration.ofSeconds(30));
        assertThat(breaker.state()).isEqualTo(CircuitBreakerState.HALF_OPEN);
        breaker.acquire();
        fhirCalls.incrementAndGet();
        breaker.recordSuccess();

        assertThat(breaker.state()).isEqualTo(CircuitBreakerState.CLOSED);
        assertThat(breaker.consecutiveFailures()).isZero();
        assertThat(fhirCalls.get()).isEqualTo(4);
        assertThat(FhirErrorCategory.CIRCUIT_OPEN.safeMessage()).doesNotContain("access_token");
    }
}
