package lab.healthcare.fhir.resilience.bulkhead;

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

import java.util.concurrent.atomic.AtomicInteger;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE)
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
class FhirBulkheadResilienceIT {

    @Autowired
    private RoutingService routingService;

    @Autowired
    private FhirBulkheadRegistry bulkheads;

    @Autowired
    private FhirCircuitBreakerRegistry circuitBreakers;

    @Autowired
    private IGenericClient fhirClient;

    @BeforeAll
    void seedSyntheticPatients() {
        SyntheticPatients.seed(fhirClient);
    }

    @Test
    void healthyLocalHapiReadUsesAPermitAndReleasesIt() {
        Patient patient = routingService.readPatient(
                RoutingRequest.readPatient("local-hapi", "patient-001", "bh-healthy"));

        assertThat(patient.getIdElement().getIdPart()).isEqualTo("patient-001");
        assertThat(bulkheads.policy().maxConcurrentOperations()).isEqualTo(5);
        assertThat(bulkheads.forDestination("local-hapi").availablePermits()).isEqualTo(5);
        assertThat(circuitBreakers.forDestination("local-hapi").state()).isEqualTo(CircuitBreakerState.CLOSED);
        assertThat(new FhirService(fhirClient).readPatient("patient-001").getIdElement().getIdPart())
                .isEqualTo("patient-001");
    }

    @Test
    void syntheticFullBulkheadBlocksBeforeFhirAndDoesNotOpenTheCircuit() {
        FhirBulkhead bulkhead = new FhirBulkhead("synthetic-full", FhirBulkheadPolicy.defaults());
        FhirCircuitBreaker breaker = new FhirCircuitBreaker(
                "synthetic-full", FhirCircuitBreakerPolicy.defaults(), MutableClock.epoch());
        AtomicInteger fhirCalls = new AtomicInteger();

        for (int i = 0; i < 5; i++) {
            bulkhead.acquire();
        }
        assertThatThrownBy(() -> bulkhead.execute(() -> {
                    fhirCalls.incrementAndGet();
                    return "should-not-run";
                }))
                .isInstanceOf(BulkheadFullException.class);
        breaker.recordFailure(FhirErrorCategory.BULKHEAD_FULL);

        assertThat(fhirCalls.get()).isZero();
        assertThat(breaker.state()).isEqualTo(CircuitBreakerState.CLOSED);
        assertThat(breaker.consecutiveFailures()).isZero();
        bulkhead.release();
        assertThat(bulkhead.execute(() -> {
            fhirCalls.incrementAndGet();
            return "ok";
        })).isEqualTo("ok");
        assertThat(fhirCalls.get()).isEqualTo(1);
        assertThat(FhirErrorCategory.BULKHEAD_FULL.safeMessage()).doesNotContain("access_token");
    }
}
