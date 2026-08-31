package lab.healthcare.fhir.routing;

import lab.healthcare.fhir.auth.oauth2.OAuth2TokenClient;
import lab.healthcare.fhir.client.FhirAccessTokenProviders;
import lab.healthcare.fhir.client.FhirClientFactory;
import lab.healthcare.fhir.exception.FhirClientException;
import lab.healthcare.fhir.exception.FhirErrorCategory;
import lab.healthcare.fhir.observability.FhirAuditOutcome;
import lab.healthcare.fhir.observability.InMemoryFhirMetricsRecorder;
import lab.healthcare.fhir.observability.LoggingFhirAuditRecorder;
import lab.healthcare.fhir.resilience.CircuitBreakerOpenException;
import lab.healthcare.fhir.resilience.CircuitBreakerState;
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
import ca.uhn.fhir.rest.server.exceptions.ResourceNotFoundException;
import org.hl7.fhir.r4.model.Patient;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Answers;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.Clock;
import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class RoutingServiceCircuitBreakerTest {

    private final LoggingFhirAuditRecorder auditRecorder = new LoggingFhirAuditRecorder();
    private final InMemoryFhirMetricsRecorder metricsRecorder = new InMemoryFhirMetricsRecorder();
    private final FhirCircuitBreakerRegistry circuitBreakers = new FhirCircuitBreakerRegistry();

    @Mock
    private FhirClientFactory mockFactory;

    @Mock(answer = Answers.RETURNS_DEEP_STUBS)
    private IGenericClient localClient;

    @Mock(answer = Answers.RETURNS_DEEP_STUBS)
    private IGenericClient otherClient;

    @Test
    void threeFailedLogicalReadsOpenTheCircuitAndThenFailFast() {
        AtomicInteger fhirCalls = new AtomicInteger();
        when(localClient.read().resource(Patient.class).withId("patient-001").execute())
                .thenAnswer(invocation -> {
                    fhirCalls.incrementAndGet();
                    throw new FhirClientConnectionException("connection refused");
                });
        RoutingService routing = routing();

        for (int i = 0; i < 3; i++) {
            assertThatThrownBy(() -> routing.readPatient(
                            RoutingRequest.readPatient("local-hapi", "patient-001", "cb-open")))
                    .isInstanceOf(FhirClientException.class)
                    .extracting(ex -> ((FhirClientException) ex).category())
                    .isEqualTo(FhirErrorCategory.CONNECTION_ERROR);
        }
        assertThat(fhirCalls.get()).isEqualTo(9);
        assertThat(circuitBreakers.forDestination("local-hapi").state()).isEqualTo(CircuitBreakerState.OPEN);

        assertThatThrownBy(() -> routing.readPatient(
                        RoutingRequest.readPatient("local-hapi", "patient-001", "cb-blocked")))
                .isInstanceOf(CircuitBreakerOpenException.class)
                .hasMessage(FhirErrorCategory.CIRCUIT_OPEN.safeMessage());

        assertThat(fhirCalls.get()).isEqualTo(9);
        assertThat(auditRecorder.recorded().getLast().error()).isEqualTo(FhirErrorCategory.CIRCUIT_OPEN);
        assertThat(auditRecorder.recorded().getLast().outcome()).isEqualTo(FhirAuditOutcome.FAILURE);
        assertThat(auditRecorder.recorded().getLast().willRetry()).isFalse();
        assertThat(auditRecorder.recorded().getLast().toLogLine()).contains("error=CIRCUIT_OPEN");
        assertThat(auditRecorder.recorded().getLast().toLogLine()).doesNotContain("access_token");
        assertThat(metricsRecorder.snapshot().totalOperations()).isEqualTo(4);
        assertThat(metricsRecorder.snapshot().failedOperations()).isEqualTo(4);
        assertThat(metricsRecorder.snapshot().retryAttempts()).isEqualTo(6);
    }

    @Test
    void notFoundDoesNotOpenTheCircuit() {
        when(localClient.read().resource(Patient.class).withId("missing").execute())
                .thenThrow(new ResourceNotFoundException("Patient/missing"));
        RoutingService routing = routing();

        for (int i = 0; i < 3; i++) {
            assertThatThrownBy(() -> routing.readPatient(
                            RoutingRequest.readPatient("local-hapi", "missing", "cb-404")))
                    .isInstanceOf(FhirClientException.class);
        }

        assertThat(circuitBreakers.forDestination("local-hapi").state()).isEqualTo(CircuitBreakerState.CLOSED);
    }

    @Test
    void failingDestinationDoesNotOpenAnotherDestination() {
        AtomicInteger localCalls = new AtomicInteger();
        when(localClient.read().resource(Patient.class).withId("patient-001").execute())
                .thenAnswer(invocation -> {
                    localCalls.incrementAndGet();
                    throw new FhirClientConnectionException("connection refused");
                });
        Patient patient = new Patient();
        patient.setId("patient-001");
        when(otherClient.read().resource(Patient.class).withId("patient-001").execute()).thenReturn(patient);
        RoutingService routing = routing();

        for (int i = 0; i < 3; i++) {
            assertThatThrownBy(() -> routing.readPatient(
                            RoutingRequest.readPatient("local-hapi", "patient-001", "cb-a")))
                    .isInstanceOf(FhirClientException.class);
        }

        Patient result = routing.readPatient(RoutingRequest.readPatient("secured-lab", "patient-001", "cb-b"));

        assertThat(result.getIdElement().getIdPart()).isEqualTo("patient-001");
        assertThat(circuitBreakers.forDestination("local-hapi").state()).isEqualTo(CircuitBreakerState.OPEN);
        assertThat(circuitBreakers.forDestination("secured-lab").state()).isEqualTo(CircuitBreakerState.CLOSED);
        assertThat(localCalls.get()).isEqualTo(9);
    }

    private RoutingService routing() {
        FhirContext context = FhirContext.forR4();
        when(mockFactory.createContext(any(FhirServerProfile.class))).thenReturn(context);
        when(mockFactory.createClient(eq(context), any(FhirServerProfile.class), any())).thenAnswer(invocation -> {
            FhirServerProfile profile = invocation.getArgument(1);
            return "secured-lab".equals(profile.name()) ? otherClient : localClient;
        });
        return new RoutingService(
                new FhirServerProfileRegistry(servers()),
                mockFactory,
                new FhirAccessTokenProviders(
                        new OAuth2TokenClient(),
                        new SmartConfigurationClient(),
                        new AuthorizationCodeClient(),
                        Clock.systemUTC()),
                auditRecorder,
                metricsRecorder,
                FhirRetryExecutor.immediate(),
                circuitBreakers,
                new FhirRateLimiterRegistry(),
                new FhirBulkheadRegistry());
    }

    private static FhirServersProperties servers() {
        return new FhirServersProperties(
                "local-hapi",
                Map.of(
                        "local-hapi", FhirServersProperties.ServerSettings.of(
                                "http://localhost:8080/fhir", "R4", true, null),
                        "secured-lab", FhirServersProperties.ServerSettings.of(
                                "http://localhost:8180/fhir", "R4", true, null)));
    }
}
