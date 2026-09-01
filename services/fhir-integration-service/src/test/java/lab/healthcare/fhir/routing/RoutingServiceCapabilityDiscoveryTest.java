package lab.healthcare.fhir.routing;

import lab.healthcare.fhir.auth.oauth2.OAuth2TokenClient;
import lab.healthcare.fhir.capability.FhirCapabilityDiscoveryServiceTest;
import lab.healthcare.fhir.capability.FhirInteraction;
import lab.healthcare.fhir.capability.FhirServerCapabilities;
import lab.healthcare.fhir.client.FhirAccessTokenProviders;
import lab.healthcare.fhir.client.FhirClientFactory;
import lab.healthcare.fhir.exception.FhirErrorCategory;
import lab.healthcare.fhir.observability.FhirAuditOperation;
import lab.healthcare.fhir.observability.FhirAuditOutcome;
import lab.healthcare.fhir.observability.InMemoryFhirMetricsRecorder;
import lab.healthcare.fhir.observability.LoggingFhirAuditRecorder;
import lab.healthcare.fhir.resilience.FhirCircuitBreakerRegistry;
import lab.healthcare.fhir.resilience.FhirRetryExecutor;
import lab.healthcare.fhir.resilience.bulkhead.FhirBulkheadRegistry;
import lab.healthcare.fhir.resilience.ratelimit.FhirRateLimiterRegistry;
import lab.healthcare.fhir.server.FhirServerProfile;
import lab.healthcare.fhir.server.FhirServerProfileRegistry;
import lab.healthcare.fhir.server.FhirServersProperties;
import lab.healthcare.fhir.smart.AuthorizationCodeClient;
import lab.healthcare.fhir.smart.SmartConfigurationClient;

import ca.uhn.fhir.context.FhirContext;
import ca.uhn.fhir.rest.client.api.IGenericClient;
import ca.uhn.fhir.rest.client.exceptions.FhirClientConnectionException;
import org.hl7.fhir.r4.model.CapabilityStatement;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Answers;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.Clock;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class RoutingServiceCapabilityDiscoveryTest {

    private final LoggingFhirAuditRecorder auditRecorder = new LoggingFhirAuditRecorder();
    private final InMemoryFhirMetricsRecorder metricsRecorder = new InMemoryFhirMetricsRecorder();

    @Mock
    private FhirClientFactory mockFactory;

    @Mock(answer = Answers.RETURNS_DEEP_STUBS)
    private IGenericClient fhirClient;

    @Test
    void unknownDestinationIsValidationErrorNotClinicalFhir() {
        RoutingService routing = routing(new FhirClientFactory(), null);

        assertThatThrownBy(() -> routing.discoverCapabilities("does-not-exist", "cap-missing"))
                .isInstanceOf(RoutingException.class)
                .hasMessageContaining("does-not-exist")
                .extracting(ex -> ((RoutingException) ex).category())
                .isEqualTo(FhirErrorCategory.VALIDATION_ERROR);

        assertThat(auditRecorder.recorded()).hasSize(1);
        assertThat(auditRecorder.recorded().getFirst().context().operation())
                .isEqualTo(FhirAuditOperation.CAPABILITY_DISCOVERY);
        assertThat(auditRecorder.recorded().getFirst().context().resourceType())
                .isEqualTo("CapabilityStatement");
        assertThat(auditRecorder.recorded().getFirst().context().resourceId()).isNull();
        assertThat(auditRecorder.recorded().getFirst().error()).isEqualTo(FhirErrorCategory.VALIDATION_ERROR);
        assertThat(auditRecorder.recorded().getFirst().toLogLine()).doesNotContain("access_token");
        assertThat(auditRecorder.recorded().getFirst().toLogLine()).doesNotContain("\"resourceType\"");
    }

    @Test
    void discoversThroughSameResiliencePipeline() {
        when(mockFactory.createContext(any(FhirServerProfile.class))).thenReturn(FhirContext.forR4());
        when(mockFactory.createClient(any(FhirContext.class), any(FhirServerProfile.class), any()))
                .thenReturn(fhirClient);
        when(fhirClient.capabilities().ofType(CapabilityStatement.class).execute())
                .thenThrow(new FhirClientConnectionException("connection refused"))
                .thenReturn(FhirCapabilityDiscoveryServiceTest.sampleStatement());
        RoutingService routing = routing(mockFactory, FhirRetryExecutor.immediate());

        FhirServerCapabilities capabilities = routing.discoverCapabilities("local-hapi", "cap-retry");

        assertThat(capabilities.supports("Patient", FhirInteraction.READ)).isTrue();
        assertThat(auditRecorder.recorded()).hasSize(2);
        assertThat(auditRecorder.recorded().getFirst().willRetry()).isTrue();
        assertThat(auditRecorder.recorded().getFirst().error()).isEqualTo(FhirErrorCategory.CONNECTION_ERROR);
        assertThat(auditRecorder.recorded().getLast().outcome()).isEqualTo(FhirAuditOutcome.SUCCESS);
        assertThat(auditRecorder.recorded().getLast().context().operation())
                .isEqualTo(FhirAuditOperation.CAPABILITY_DISCOVERY);
        assertThat(metricsRecorder.snapshot().totalOperations()).isEqualTo(1);
        assertThat(metricsRecorder.snapshot().operationsByType())
                .containsEntry(FhirAuditOperation.CAPABILITY_DISCOVERY.name(), 1L);
        verify(fhirClient.capabilities().ofType(CapabilityStatement.class), times(2)).execute();
    }

    private RoutingService routing(FhirClientFactory factory, FhirRetryExecutor retryExecutor) {
        return new RoutingService(
                new FhirServerProfileRegistry(twoServers()),
                factory,
                new FhirAccessTokenProviders(
                        new OAuth2TokenClient(),
                        new SmartConfigurationClient(),
                        new AuthorizationCodeClient(),
                        Clock.systemUTC()),
                auditRecorder,
                metricsRecorder,
                retryExecutor == null ? FhirRetryExecutor.immediate() : retryExecutor,
                new FhirCircuitBreakerRegistry(),
                new FhirRateLimiterRegistry(),
                new FhirBulkheadRegistry());
    }

    private static FhirServersProperties twoServers() {
        return new FhirServersProperties(
                "local-hapi",
                Map.of(
                        "local-hapi",
                        FhirServersProperties.ServerSettings.of("http://localhost:8080/fhir", "R4", true, null),
                        "example-org",
                        FhirServersProperties.ServerSettings.of("https://example.org/fhir", "R4", false, null)));
    }
}
