package lab.healthcare.fhir.routing;

import lab.healthcare.fhir.auth.oauth2.OAuth2TokenClient;
import lab.healthcare.fhir.client.FhirAccessTokenProviders;
import lab.healthcare.fhir.client.FhirClientFactory;
import lab.healthcare.fhir.exception.FhirClientException;
import lab.healthcare.fhir.exception.FhirErrorCategory;
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
import ca.uhn.fhir.rest.server.exceptions.ResourceNotFoundException;
import org.hl7.fhir.r4.model.Patient;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Answers;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.net.SocketTimeoutException;
import java.time.Clock;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class RoutingServiceRetryTest {

    private final LoggingFhirAuditRecorder auditRecorder = new LoggingFhirAuditRecorder();
    private final InMemoryFhirMetricsRecorder metricsRecorder = new InMemoryFhirMetricsRecorder();

    @Mock
    private FhirClientFactory mockFactory;

    @Mock(answer = Answers.RETURNS_DEEP_STUBS)
    private IGenericClient fhirClient;

    @Test
    void timeoutThenSuccessIsOneLogicalOperation() {
        Patient patient = patient("patient-001");
        when(fhirClient.read().resource(Patient.class).withId("patient-001").execute())
                .thenThrow(new FhirClientConnectionException("timed out", new SocketTimeoutException("Read timed out")))
                .thenReturn(patient);
        RoutingService routing = routing();

        Patient result = routing.readPatient(RoutingRequest.readPatient("local-hapi", "patient-001", "retry-ok"));

        assertThat(result.getIdElement().getIdPart()).isEqualTo("patient-001");
        assertThat(auditRecorder.recorded()).hasSize(2);
        assertThat(auditRecorder.recorded().getFirst().outcome()).isEqualTo(FhirAuditOutcome.FAILURE);
        assertThat(auditRecorder.recorded().getFirst().willRetry()).isTrue();
        assertThat(auditRecorder.recorded().getFirst().attempt()).isEqualTo(1);
        assertThat(auditRecorder.recorded().getFirst().error()).isEqualTo(FhirErrorCategory.TIMEOUT);
        assertThat(auditRecorder.recorded().getLast().outcome()).isEqualTo(FhirAuditOutcome.SUCCESS);
        assertThat(auditRecorder.recorded().getLast().attempt()).isEqualTo(2);
        assertThat(auditRecorder.recorded()).allSatisfy(event ->
                assertThat(event.context().correlationId()).isEqualTo("retry-ok"));
        assertThat(metricsRecorder.snapshot().totalOperations()).isEqualTo(1);
        assertThat(metricsRecorder.snapshot().successfulOperations()).isEqualTo(1);
        assertThat(metricsRecorder.snapshot().failedOperations()).isZero();
        assertThat(metricsRecorder.snapshot().operationsRetried()).isEqualTo(1);
        assertThat(metricsRecorder.snapshot().retryAttempts()).isEqualTo(1);
        assertThat(auditRecorder.recorded().getFirst().toLogLine()).contains("retry=true");
        assertThat(auditRecorder.recorded().getFirst().toLogLine()).doesNotContain("access_token");
        assertThat(auditRecorder.recorded().getFirst().toLogLine()).doesNotContain("Garcia");
    }

    @Test
    void notFoundIsNotRetried() {
        when(fhirClient.read().resource(Patient.class).withId("missing").execute())
                .thenThrow(new ResourceNotFoundException("Patient/missing"));

        assertThatThrownBy(() -> routing().readPatient(RoutingRequest.readPatient("local-hapi", "missing", "retry-404")))
                .isInstanceOf(FhirClientException.class)
                .extracting(ex -> ((FhirClientException) ex).category())
                .isEqualTo(FhirErrorCategory.NOT_FOUND);

        assertThat(auditRecorder.recorded()).hasSize(1);
        assertThat(auditRecorder.recorded().getFirst().willRetry()).isFalse();
        assertThat(metricsRecorder.snapshot().totalOperations()).isEqualTo(1);
        assertThat(metricsRecorder.snapshot().failedOperations()).isEqualTo(1);
        assertThat(metricsRecorder.snapshot().operationsRetried()).isZero();
    }

    @Test
    void exhaustedConnectionErrorsPreserveStructuredFailure() {
        when(fhirClient.read().resource(Patient.class).withId("patient-001").execute())
                .thenThrow(new FhirClientConnectionException("connection refused"));

        assertThatThrownBy(() -> routing().readPatient(
                        RoutingRequest.readPatient("local-hapi", "patient-001", "retry-exhaust")))
                .isInstanceOf(FhirClientException.class)
                .extracting(ex -> ((FhirClientException) ex).category())
                .isEqualTo(FhirErrorCategory.CONNECTION_ERROR);

        assertThat(auditRecorder.recorded()).hasSize(3);
        assertThat(auditRecorder.recorded().get(0).willRetry()).isTrue();
        assertThat(auditRecorder.recorded().get(2).willRetry()).isFalse();
        assertThat(metricsRecorder.snapshot().totalOperations()).isEqualTo(1);
        assertThat(metricsRecorder.snapshot().failedOperations()).isEqualTo(1);
        assertThat(metricsRecorder.snapshot().successfulOperations()).isZero();
        assertThat(metricsRecorder.snapshot().retryAttempts()).isEqualTo(2);
        assertThat(metricsRecorder.snapshot().toSummaryLine()).doesNotContain("patient-001");
    }

    private RoutingService routing() {
        FhirContext context = FhirContext.forR4();
        when(mockFactory.createContext(any(FhirServerProfile.class))).thenReturn(context);
        when(mockFactory.createClient(eq(context), any(FhirServerProfile.class), any())).thenReturn(fhirClient);
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
                new FhirCircuitBreakerRegistry(),
                new FhirRateLimiterRegistry(),
                new FhirBulkheadRegistry());
    }

    private static Patient patient(String id) {
        Patient patient = new Patient();
        patient.setId(id);
        patient.addName().setFamily("Garcia").addGiven("Maria");
        return patient;
    }

    private static FhirServersProperties servers() {
        return new FhirServersProperties(
                "local-hapi",
                Map.of("local-hapi", FhirServersProperties.ServerSettings.of(
                        "http://localhost:8080/fhir", "R4", true, null)));
    }
}
