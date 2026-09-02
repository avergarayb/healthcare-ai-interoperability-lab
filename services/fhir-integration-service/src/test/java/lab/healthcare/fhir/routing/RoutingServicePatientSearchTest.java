package lab.healthcare.fhir.routing;

import lab.healthcare.fhir.auth.AccessToken;
import lab.healthcare.fhir.auth.IssuedAccessTokenProvider;
import lab.healthcare.fhir.auth.oauth2.OAuth2TokenClient;
import lab.healthcare.fhir.client.FhirAccessTokenProviders;
import lab.healthcare.fhir.client.FhirClientFactory;
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
import ca.uhn.fhir.rest.gclient.ICriterion;
import org.hl7.fhir.r4.model.Bundle;
import org.hl7.fhir.r4.model.Patient;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Answers;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.Clock;
import java.time.Instant;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class RoutingServicePatientSearchTest {

    private final LoggingFhirAuditRecorder auditRecorder = new LoggingFhirAuditRecorder();
    private final InMemoryFhirMetricsRecorder metricsRecorder = new InMemoryFhirMetricsRecorder();

    @Mock
    private FhirClientFactory mockFactory;

    @Mock(answer = Answers.RETURNS_DEEP_STUBS)
    private IGenericClient fhirClient;

    @Test
    void searchPatientsUsesProvidedTokenProviderAndAuditsSafely() {
        IssuedAccessTokenProvider issued = new IssuedAccessTokenProvider(
                new AccessToken("routing-secret-token", Instant.parse("2026-09-02T20:00:00Z")));
        Bundle bundle = new Bundle();
        bundle.setType(Bundle.BundleType.SEARCHSET);
        when(mockFactory.createContext(any(FhirServerProfile.class))).thenReturn(FhirContext.forR4());
        when(mockFactory.createClient(any(FhirContext.class), any(FhirServerProfile.class), eq(issued)))
                .thenReturn(fhirClient);
        when(fhirClient.search()
                        .forResource(eq(Patient.class))
                        .where(any(ICriterion.class))
                        .count(1)
                        .returnBundle(eq(Bundle.class))
                        .execute())
                .thenReturn(bundle);
        RoutingService routing = routing(mockFactory);

        Bundle actual = routing.searchPatients("local-hapi", issued, "LabNoMatch", "search-1");

        assertThat(actual.getType()).isEqualTo(Bundle.BundleType.SEARCHSET);
        assertThat(auditRecorder.recorded()).hasSize(1);
        assertThat(auditRecorder.recorded().getFirst().outcome()).isEqualTo(FhirAuditOutcome.SUCCESS);
        assertThat(auditRecorder.recorded().getFirst().context().operation())
                .isEqualTo(FhirAuditOperation.PATIENT_SEARCH);
        assertThat(auditRecorder.recorded().getFirst().context().resourceType()).isEqualTo("Patient");
        assertThat(auditRecorder.recorded().getFirst().toLogLine()).doesNotContain("routing-secret-token");
        assertThat(auditRecorder.recorded().getFirst().toLogLine()).doesNotContain("access_token");
        assertThat(metricsRecorder.snapshot().operationsByType())
                .containsEntry(FhirAuditOperation.PATIENT_SEARCH.name(), 1L);
        verify(mockFactory).createClient(any(FhirContext.class), any(FhirServerProfile.class), eq(issued));
    }

    @Test
    void searchPatientsRequiresTokenProvider() {
        RoutingService routing = routing(new FhirClientFactory());

        assertThatThrownBy(() -> routing.searchPatients("local-hapi", null, "LabNoMatch"))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("Access token provider");
        assertThatThrownBy(() -> routing.searchPatients("local-hapi", issuedForValidation(), "  "))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("Patient name");
    }

    private static IssuedAccessTokenProvider issuedForValidation() {
        return new IssuedAccessTokenProvider(
                new AccessToken("routing-secret-token", Instant.parse("2026-09-02T20:00:00Z")));
    }

    private RoutingService routing(FhirClientFactory factory) {
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
                FhirRetryExecutor.immediate(),
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
