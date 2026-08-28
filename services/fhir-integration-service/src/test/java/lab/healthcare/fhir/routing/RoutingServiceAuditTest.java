package lab.healthcare.fhir.routing;

import lab.healthcare.fhir.auth.oauth2.OAuth2TokenClient;
import lab.healthcare.fhir.client.FhirAccessTokenProviders;
import lab.healthcare.fhir.client.FhirClientFactory;
import lab.healthcare.fhir.exception.FhirErrorCategory;
import lab.healthcare.fhir.observability.FhirAuditEvent;
import lab.healthcare.fhir.observability.FhirAuditOperation;
import lab.healthcare.fhir.observability.FhirAuditOutcome;
import lab.healthcare.fhir.observability.InMemoryFhirMetricsRecorder;
import lab.healthcare.fhir.observability.LoggingFhirAuditRecorder;
import lab.healthcare.fhir.server.FhirServerProfileRegistry;
import lab.healthcare.fhir.server.FhirServersProperties;
import lab.healthcare.fhir.smart.AuthorizationCodeClient;
import lab.healthcare.fhir.smart.SmartConfigurationClient;

import org.junit.jupiter.api.Test;

import java.time.Clock;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class RoutingServiceAuditTest {

    private final LoggingFhirAuditRecorder recorder = new LoggingFhirAuditRecorder();
    private final RoutingService routing = new RoutingService(
            new FhirServerProfileRegistry(twoServers()),
            new FhirClientFactory(),
            new FhirAccessTokenProviders(
                    new OAuth2TokenClient(),
                    new SmartConfigurationClient(),
                    new AuthorizationCodeClient(),
                    Clock.systemUTC()),
            recorder,
            new InMemoryFhirMetricsRecorder());

    @Test
    void unknownDestinationRecordsFailureWithoutFallingBack() {
        assertThatThrownBy(() -> routing.readPatient(
                        RoutingRequest.readPatient("does-not-exist", "patient-001", "corr-fail")))
                .isInstanceOf(RoutingException.class);

        FhirAuditEvent event = recorder.recorded().getFirst();
        assertThat(event.outcome()).isEqualTo(FhirAuditOutcome.FAILURE);
        assertThat(event.error()).isEqualTo(FhirErrorCategory.VALIDATION_ERROR);
        assertThat(event.context().correlationId()).isEqualTo("corr-fail");
        assertThat(event.context().destination()).isEqualTo("does-not-exist");
        assertThat(event.context().operation()).isEqualTo(FhirAuditOperation.READ);
        assertThat(event.context().resourceType()).isEqualTo("Patient");
        assertThat(event.context().resourceId()).isEqualTo("patient-001");
        assertThat(event.durationMs()).isGreaterThanOrEqualTo(0);
        assertThat(event.toLogLine()).doesNotContain("access_token");
        assertThat(event.toLogLine()).doesNotContain("client_secret");
        assertThat(event.toLogLine()).doesNotContain("Bearer ");
    }

    @Test
    void disabledDestinationRecordsFailureWithoutFallingBack() {
        assertThatThrownBy(() -> routing.readPatient(
                        RoutingRequest.readPatient("example-org", "patient-001", "corr-disabled")))
                .isInstanceOf(RoutingException.class);

        FhirAuditEvent event = recorder.recorded().getFirst();
        assertThat(event.error()).isEqualTo(FhirErrorCategory.VALIDATION_ERROR);
        assertThat(event.context().destination()).isEqualTo("example-org");
        assertThat(event.context().correlationId()).isEqualTo("corr-disabled");
        assertThat(event.toLogLine()).contains("error=VALIDATION_ERROR");
    }

    @Test
    void generatesCorrelationIdWhenCallerOmitsOne() {
        assertThatThrownBy(() -> routing.readPatient(RoutingRequest.readPatient("does-not-exist", "patient-001")))
                .isInstanceOf(RoutingException.class);

        assertThat(recorder.recorded().getFirst().context().correlationId()).isNotBlank();
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
