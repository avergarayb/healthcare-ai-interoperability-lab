package lab.healthcare.fhir.exception;

import lab.healthcare.fhir.client.SyntheticPatients;
import lab.healthcare.fhir.observability.FhirAuditEvent;
import lab.healthcare.fhir.observability.FhirAuditOutcome;
import lab.healthcare.fhir.observability.FhirMetricSnapshot;
import lab.healthcare.fhir.observability.FhirMetricsRecorder;
import lab.healthcare.fhir.observability.LoggingFhirAuditRecorder;
import lab.healthcare.fhir.routing.RoutingException;
import lab.healthcare.fhir.routing.RoutingRequest;
import lab.healthcare.fhir.routing.RoutingService;

import ca.uhn.fhir.rest.client.api.IGenericClient;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestInstance;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE)
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
class FhirErrorHandlingIT {

    @Autowired
    private RoutingService routingService;

    @Autowired
    private LoggingFhirAuditRecorder auditRecorder;

    @Autowired
    private FhirMetricsRecorder metricsRecorder;

    @Autowired
    private IGenericClient fhirClient;

    @BeforeAll
    void seedSyntheticPatients() {
        SyntheticPatients.seed(fhirClient);
    }

    @Test
    void missingPatientIsNotFoundAndIsAuditedAndCounted() {
        FhirMetricSnapshot before = metricsRecorder.snapshot();

        assertThatThrownBy(() -> routingService.readPatient(
                        RoutingRequest.readPatient("local-hapi", "does-not-exist", "error-404-023")))
                .isInstanceOf(FhirClientException.class)
                .satisfies(ex -> {
                    FhirClientException failure = (FhirClientException) ex;
                    assertThat(failure.category()).isEqualTo(FhirErrorCategory.NOT_FOUND);
                    assertThat(failure.details().status()).isEqualTo(404);
                    assertThat(failure.getMessage()).isEqualTo("FHIR resource not found");
                    assertThat(failure.getMessage()).doesNotContain("access_token");
                    assertThat(failure.getMessage()).doesNotContain("Garcia");
                });

        FhirAuditEvent event = event("error-404-023");
        FhirMetricSnapshot after = metricsRecorder.snapshot();
        assertThat(event.outcome()).isEqualTo(FhirAuditOutcome.FAILURE);
        assertThat(event.error()).isEqualTo(FhirErrorCategory.NOT_FOUND);
        assertThat(event.status()).isEqualTo(404);
        assertThat(event.toLogLine()).contains("error=NOT_FOUND");
        assertThat(event.toLogLine()).doesNotContain("access_token");
        assertThat(after.failedOperations()).isEqualTo(before.failedOperations() + 1);
        assertThat(after.toSummaryLine()).doesNotContain("error-404-023");
        assertThat(after.toSummaryLine()).doesNotContain("NOT_FOUND");
    }

    @Test
    void unknownDestinationRemainsARoutingValidationError() {
        FhirMetricSnapshot before = metricsRecorder.snapshot();

        assertThatThrownBy(() -> routingService.readPatient(
                        RoutingRequest.readPatient("does-not-exist", "patient-001", "error-routing-023")))
                .isInstanceOf(RoutingException.class)
                .isNotInstanceOf(FhirClientException.class)
                .satisfies(ex -> {
                    RoutingException failure = (RoutingException) ex;
                    assertThat(failure.category()).isEqualTo(FhirErrorCategory.VALIDATION_ERROR);
                    assertThat(failure.details().destination()).isEqualTo("does-not-exist");
                    assertThat(failure.getMessage()).contains("FHIR destination not found");
                    assertThat(failure.getMessage()).doesNotContain("access_token");
                });

        FhirAuditEvent event = event("error-routing-023");
        FhirMetricSnapshot after = metricsRecorder.snapshot();
        assertThat(event.outcome()).isEqualTo(FhirAuditOutcome.FAILURE);
        assertThat(event.error()).isEqualTo(FhirErrorCategory.VALIDATION_ERROR);
        assertThat(event.toLogLine()).contains("error=VALIDATION_ERROR");
        assertThat(after.failedOperations()).isEqualTo(before.failedOperations() + 1);
        assertThat(after.toSummaryLine()).doesNotContain("patient-001");
    }

    private FhirAuditEvent event(String correlationId) {
        return auditRecorder.recorded().stream()
                .filter(candidate -> correlationId.equals(candidate.context().correlationId()))
                .reduce((first, second) -> second)
                .orElseThrow(() -> new AssertionError("No audit event for " + correlationId));
    }
}
