package lab.healthcare.fhir.resilience;

import lab.healthcare.fhir.client.FhirService;
import lab.healthcare.fhir.client.SyntheticPatients;
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

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE)
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
class FhirResiliencePipelineIT {

    @Autowired
    private RoutingService routingService;

    @Autowired
    private FhirResilienceProperties properties;

    @Autowired
    private FhirCircuitBreakerRegistry circuitBreakers;

    @Autowired
    private IGenericClient fhirClient;

    @BeforeAll
    void seedSyntheticPatients() {
        SyntheticPatients.seed(fhirClient);
    }

    @Test
    void healthyRoutedReadUsesConfiguredPipelineAndLeavesCircuitClosed() {
        Patient patient = routingService.readPatient(
                RoutingRequest.readPatient("local-hapi", "patient-001", "pipe-healthy"));

        assertThat(patient.getIdElement().getIdPart()).isEqualTo("patient-001");
        assertThat(properties.retry().maxAttempts()).isEqualTo(3);
        assertThat(properties.retry().initialBackoff()).isEqualTo(Duration.ofMillis(100));
        assertThat(properties.circuitBreaker().failureThreshold()).isEqualTo(3);
        assertThat(properties.rateLimit().maxOperations()).isEqualTo(10);
        assertThat(properties.bulkhead().maxConcurrentOperations()).isEqualTo(5);
        assertThat(circuitBreakers.forDestination("local-hapi").state()).isEqualTo(CircuitBreakerState.CLOSED);
        assertThat(new FhirService(fhirClient).readPatient("patient-001").getIdElement().getIdPart())
                .isEqualTo("patient-001");
        assertThat(FhirService.class.getPackageName()).doesNotContain("resilience");
    }
}
