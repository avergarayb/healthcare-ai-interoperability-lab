package lab.healthcare.fhir.routing;

import lab.healthcare.fhir.auth.oauth2.OAuth2TokenClient;
import lab.healthcare.fhir.client.FhirAccessTokenProviders;
import lab.healthcare.fhir.client.FhirClientFactory;
import lab.healthcare.fhir.observability.FhirMetricSnapshot;
import lab.healthcare.fhir.observability.InMemoryFhirMetricsRecorder;
import lab.healthcare.fhir.observability.LoggingFhirAuditRecorder;
import lab.healthcare.fhir.resilience.FhirCircuitBreakerRegistry;
import lab.healthcare.fhir.resilience.FhirRetryExecutor;
import lab.healthcare.fhir.resilience.bulkhead.FhirBulkheadRegistry;
import lab.healthcare.fhir.resilience.ratelimit.FhirRateLimiterRegistry;
import lab.healthcare.fhir.server.FhirServerProfileRegistry;
import lab.healthcare.fhir.server.FhirServersProperties;
import lab.healthcare.fhir.smart.AuthorizationCodeClient;
import lab.healthcare.fhir.smart.SmartConfigurationClient;

import org.junit.jupiter.api.Test;

import java.time.Clock;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class RoutingServiceMetricsTest {

    private final LoggingFhirAuditRecorder auditRecorder = new LoggingFhirAuditRecorder();
    private final InMemoryFhirMetricsRecorder metricsRecorder = new InMemoryFhirMetricsRecorder();
    private final RoutingService routing = new RoutingService(
            new FhirServerProfileRegistry(twoServers()),
            new FhirClientFactory(),
            new FhirAccessTokenProviders(
                    new OAuth2TokenClient(),
                    new SmartConfigurationClient(),
                    new AuthorizationCodeClient(),
                    Clock.systemUTC()),
            auditRecorder,
            metricsRecorder,
            FhirRetryExecutor.immediate(),
            new FhirCircuitBreakerRegistry(),
            new FhirRateLimiterRegistry(),
            new FhirBulkheadRegistry());

    @Test
    void unknownDestinationRecordsIndependentAuditAndFailureMetric() {
        assertThatThrownBy(() -> routing.readPatient(
                        RoutingRequest.readPatient("does-not-exist", "patient-001", "corr-metrics-fail")))
                .isInstanceOf(RoutingException.class);

        FhirMetricSnapshot snapshot = metricsRecorder.snapshot();
        assertThat(auditRecorder.recorded()).hasSize(1);
        assertThat(auditRecorder.recorded().getFirst().context().correlationId()).isEqualTo("corr-metrics-fail");
        assertThat(snapshot.totalOperations()).isEqualTo(1);
        assertThat(snapshot.failedOperations()).isEqualTo(1);
        assertThat(snapshot.successfulOperations()).isZero();
        assertThat(snapshot.operationsByDestination()).containsEntry("does-not-exist", 1L);
        assertThat(snapshot.operationsByType()).containsEntry("READ", 1L);
        assertThat(snapshot.operationsByResourceType()).containsEntry("Patient", 1L);
        assertThat(snapshot.toSummaryLine()).doesNotContain("corr-metrics-fail");
        assertThat(snapshot.toSummaryLine()).doesNotContain("patient-001");
        assertThat(snapshot.toSummaryLine()).doesNotContain("access_token");
    }

    @Test
    void disabledDestinationIncrementsFailureMetricWithoutFallback() {
        assertThatThrownBy(() -> routing.readPatient(
                        RoutingRequest.readPatient("example-org", "patient-001", "corr-metrics-disabled")))
                .isInstanceOf(RoutingException.class);

        FhirMetricSnapshot snapshot = metricsRecorder.snapshot();
        assertThat(snapshot.failedOperations()).isEqualTo(1);
        assertThat(snapshot.operationsByDestination()).containsEntry("example-org", 1L);
        assertThat(snapshot.toSummaryLine()).doesNotContain("corr-metrics-disabled");
    }

    private static FhirServersProperties twoServers() {
        return new FhirServersProperties(
                "local-hapi",
                Map.of(
                        "local-hapi", new FhirServersProperties.ServerSettings(
                                "http://localhost:8080/fhir", "R4", true, null),
                        "example-org", new FhirServersProperties.ServerSettings(
                                "https://example.org/fhir", "R4", false, null)));
    }
}
