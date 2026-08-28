package lab.healthcare.fhir.observability;

import lab.healthcare.fhir.client.SyntheticPatients;
import lab.healthcare.fhir.routing.RoutingException;
import lab.healthcare.fhir.routing.RoutingRequest;
import lab.healthcare.fhir.routing.RoutingService;

import ca.uhn.fhir.rest.client.api.IGenericClient;
import org.hl7.fhir.r4.model.Patient;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestInstance;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE)
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
class FhirAuditObservabilityIT {

    @Autowired
    private RoutingService routingService;

    @Autowired
    private LoggingFhirAuditRecorder auditRecorder;

    @Autowired
    private IGenericClient fhirClient;

    @BeforeAll
    void seedSyntheticPatients() {
        SyntheticPatients.seed(fhirClient);
    }

    @Test
    void routedPatientReadProducesSuccessAuditEvent() {
        Patient patient = routingService.readPatient(
                RoutingRequest.readPatient("local-hapi", "patient-001", "audit-success-021"));

        FhirAuditEvent event = event("audit-success-021");
        assertThat(patient.getIdElement().getIdPart()).isEqualTo("patient-001");
        assertThat(patient.getNameFirstRep().getFamily()).isEqualTo("Garcia");
        assertThat(event.outcome()).isEqualTo(FhirAuditOutcome.SUCCESS);
        assertThat(event.status()).isEqualTo(200);
        assertThat(event.context().destination()).isEqualTo("local-hapi");
        assertThat(event.context().operation()).isEqualTo(FhirAuditOperation.READ);
        assertThat(event.context().resourceType()).isEqualTo("Patient");
        assertThat(event.context().resourceId()).isEqualTo("patient-001");
        assertThat(event.durationMs()).isGreaterThanOrEqualTo(0);
        assertThat(event.toLogLine()).contains("FHIR_AUDIT");
        assertThat(event.toLogLine()).doesNotContain("Garcia");
        assertThat(event.toLogLine()).doesNotContain("access_token");
        assertThat(event.toLogLine()).doesNotContain("client_secret");
        assertThat(event.toLogLine()).doesNotContain("Bearer ");
    }

    @Test
    void unknownDestinationProducesFailureAuditEvent() {
        assertThatThrownBy(() -> routingService.readPatient(
                        RoutingRequest.readPatient("does-not-exist", "patient-001", "audit-failure-021")))
                .isInstanceOf(RoutingException.class);

        FhirAuditEvent event = event("audit-failure-021");
        assertThat(event.outcome()).isEqualTo(FhirAuditOutcome.FAILURE);
        assertThat(event.error()).isEqualTo(FhirAuditError.DESTINATION_NOT_FOUND);
        assertThat(event.context().destination()).isEqualTo("does-not-exist");
        assertThat(event.context().resourceId()).isEqualTo("patient-001");
        assertThat(event.toLogLine()).contains("error=DESTINATION_NOT_FOUND");
        assertThat(event.toLogLine()).doesNotContain("access_token");
    }

    private FhirAuditEvent event(String correlationId) {
        return auditRecorder.recorded().stream()
                .filter(candidate -> correlationId.equals(candidate.context().correlationId()))
                .reduce((first, second) -> second)
                .orElseThrow(() -> new AssertionError("No audit event for " + correlationId));
    }
}
