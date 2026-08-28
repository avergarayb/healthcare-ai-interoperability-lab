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
class FhirMetricsObservabilityIT {

    @Autowired
    private RoutingService routingService;

    @Autowired
    private FhirMetricsRecorder metricsRecorder;

    @Autowired
    private IGenericClient fhirClient;

    @BeforeAll
    void seedSyntheticPatients() {
        SyntheticPatients.seed(fhirClient);
    }

    @Test
    void routedReadAndUnknownDestinationAggregateSuccessAndFailureMetrics() {
        FhirMetricSnapshot before = metricsRecorder.snapshot();

        Patient patient = routingService.readPatient(
                RoutingRequest.readPatient("local-hapi", "patient-001", "metrics-success-022"));
        assertThatThrownBy(() -> routingService.readPatient(
                        RoutingRequest.readPatient("does-not-exist", "patient-001", "metrics-failure-022")))
                .isInstanceOf(RoutingException.class);

        FhirMetricSnapshot after = metricsRecorder.snapshot();
        assertThat(patient.getIdElement().getIdPart()).isEqualTo("patient-001");
        assertThat(after.totalOperations()).isEqualTo(before.totalOperations() + 2);
        assertThat(after.successfulOperations()).isEqualTo(before.successfulOperations() + 1);
        assertThat(after.failedOperations()).isEqualTo(before.failedOperations() + 1);
        assertThat(after.operationsByType().get("READ")).isEqualTo(nullToZero(before.operationsByType().get("READ")) + 2);
        assertThat(after.operationsByDestination().get("local-hapi"))
                .isEqualTo(nullToZero(before.operationsByDestination().get("local-hapi")) + 1);
        assertThat(after.operationsByDestination().get("does-not-exist"))
                .isEqualTo(nullToZero(before.operationsByDestination().get("does-not-exist")) + 1);
        assertThat(after.operationsByResourceType().get("Patient"))
                .isEqualTo(nullToZero(before.operationsByResourceType().get("Patient")) + 2);
        assertThat(after.totalDurationMs()).isGreaterThanOrEqualTo(before.totalDurationMs());
        assertThat(after.averageDurationMs()).isGreaterThanOrEqualTo(0);
        assertThat(after.toSummaryLine()).doesNotContain("patient-001");
        assertThat(after.toSummaryLine()).doesNotContain("metrics-success-022");
        assertThat(after.toSummaryLine()).doesNotContain("access_token");
        assertThat(after.toSummaryLine()).doesNotContain("Garcia");
    }

    private static long nullToZero(Long value) {
        return value == null ? 0L : value;
    }
}
