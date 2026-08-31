package lab.healthcare.fhir.resilience;

import lab.healthcare.fhir.auth.oauth2.OAuth2TokenClient;
import lab.healthcare.fhir.client.FhirAccessTokenProviders;
import lab.healthcare.fhir.client.FhirClientFactory;
import lab.healthcare.fhir.exception.FhirClientException;
import lab.healthcare.fhir.exception.FhirErrorCategory;
import lab.healthcare.fhir.observability.FhirAuditOutcome;
import lab.healthcare.fhir.observability.InMemoryFhirMetricsRecorder;
import lab.healthcare.fhir.observability.LoggingFhirAuditRecorder;
import lab.healthcare.fhir.resilience.bulkhead.BulkheadFullException;
import lab.healthcare.fhir.resilience.bulkhead.FhirBulkheadRegistry;
import lab.healthcare.fhir.resilience.ratelimit.FhirRateLimiterRegistry;
import lab.healthcare.fhir.resilience.ratelimit.RateLimitExceededException;
import lab.healthcare.fhir.routing.RoutingRequest;
import lab.healthcare.fhir.routing.RoutingService;
import lab.healthcare.fhir.server.FhirServerProfile;
import lab.healthcare.fhir.server.FhirServerProfileRegistry;
import lab.healthcare.fhir.server.FhirServersProperties;
import lab.healthcare.fhir.smart.AuthorizationCodeClient;
import lab.healthcare.fhir.smart.SmartConfigurationClient;

import ca.uhn.fhir.context.FhirContext;
import ca.uhn.fhir.rest.client.api.IGenericClient;
import ca.uhn.fhir.rest.client.exceptions.FhirClientConnectionException;
import org.hl7.fhir.r4.model.Patient;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Answers;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.net.SocketTimeoutException;
import java.time.Clock;
import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class FhirResiliencePipelineTest {

    private final LoggingFhirAuditRecorder auditRecorder = new LoggingFhirAuditRecorder();
    private final InMemoryFhirMetricsRecorder metricsRecorder = new InMemoryFhirMetricsRecorder();
    private final MutableClock clock = MutableClock.epoch();
    private final FhirResilienceProperties properties = FhirResilienceProperties.defaults();
    private final FhirCircuitBreakerRegistry circuitBreakers =
            FhirCircuitBreakerRegistry.of(properties.circuitBreakerPolicy(), clock);
    private final FhirRateLimiterRegistry rateLimiters =
            FhirRateLimiterRegistry.of(properties.rateLimiterPolicy(), clock);
    private final FhirBulkheadRegistry bulkheads = FhirBulkheadRegistry.of(properties.bulkheadPolicy());

    @Mock
    private FhirClientFactory mockFactory;

    @Mock(answer = Answers.RETURNS_DEEP_STUBS)
    private IGenericClient fhirClient;

    @Test
    void successfulReadGoesThroughTheFullPipeline() {
        AtomicInteger fhirCalls = new AtomicInteger();
        stubRead(invocation -> {
            fhirCalls.incrementAndGet();
            return patient();
        });

        Patient result = routing().readPatient(RoutingRequest.readPatient("local-hapi", "patient-001", "pipe-ok"));

        assertThat(result.getIdElement().getIdPart()).isEqualTo("patient-001");
        assertThat(fhirCalls.get()).isEqualTo(1);
        assertThat(circuitBreakers.forDestination("local-hapi").state()).isEqualTo(CircuitBreakerState.CLOSED);
        assertThat(bulkheads.forDestination("local-hapi").availablePermits()).isEqualTo(5);
        assertThat(metricsRecorder.snapshot().successfulOperations()).isEqualTo(1);
        assertThat(metricsRecorder.snapshot().retryAttempts()).isZero();
        assertThat(auditRecorder.recorded().getFirst().toLogLine()).doesNotContain("access_token");
        assertThat(auditRecorder.recorded().getFirst().toLogLine()).doesNotContain("Garcia");
    }

    @Test
    void rateLimitedStopsBeforeBulkheadCircuitRetryAndFhir() {
        AtomicInteger fhirCalls = new AtomicInteger();
        stubRead(invocation -> {
            fhirCalls.incrementAndGet();
            return patient();
        });
        RoutingService routing = routing();
        for (int i = 0; i < 10; i++) {
            routing.readPatient(RoutingRequest.readPatient("local-hapi", "patient-001", "pipe-rl"));
        }

        assertThatThrownBy(() -> routing.readPatient(
                        RoutingRequest.readPatient("local-hapi", "patient-001", "pipe-rl-block")))
                .isInstanceOf(RateLimitExceededException.class);

        assertThat(fhirCalls.get()).isEqualTo(10);
        assertThat(bulkheads.forDestination("local-hapi").availablePermits()).isEqualTo(5);
        assertThat(circuitBreakers.forDestination("local-hapi").state()).isEqualTo(CircuitBreakerState.CLOSED);
        assertThat(auditRecorder.recorded().getLast().error()).isEqualTo(FhirErrorCategory.RATE_LIMITED);
        assertThat(metricsRecorder.snapshot().retryAttempts()).isZero();
    }

    @Test
    void bulkheadFullStopsBeforeCircuitRetryAndFhir() {
        AtomicInteger fhirCalls = new AtomicInteger();
        for (int i = 0; i < 5; i++) {
            bulkheads.forDestination("local-hapi").acquire();
        }

        assertThatThrownBy(() -> routing().readPatient(
                        RoutingRequest.readPatient("local-hapi", "patient-001", "pipe-bh-block")))
                .isInstanceOf(BulkheadFullException.class);

        assertThat(fhirCalls.get()).isZero();
        assertThat(circuitBreakers.forDestination("local-hapi").state()).isEqualTo(CircuitBreakerState.CLOSED);
        assertThat(auditRecorder.recorded().getLast().error()).isEqualTo(FhirErrorCategory.BULKHEAD_FULL);
        assertThat(metricsRecorder.snapshot().retryAttempts()).isZero();
    }

    @Test
    void transientFailureThenSuccessIsOneLogicalOperation() {
        AtomicInteger fhirCalls = new AtomicInteger();
        stubRead(invocation -> {
            if (fhirCalls.incrementAndGet() == 1) {
                throw new FhirClientConnectionException("timed out", new SocketTimeoutException("Read timed out"));
            }
            return patient();
        });

        Patient result = routing().readPatient(RoutingRequest.readPatient("local-hapi", "patient-001", "pipe-retry"));

        assertThat(result.getIdElement().getIdPart()).isEqualTo("patient-001");
        assertThat(fhirCalls.get()).isEqualTo(2);
        assertThat(circuitBreakers.forDestination("local-hapi").state()).isEqualTo(CircuitBreakerState.CLOSED);
        assertThat(metricsRecorder.snapshot().totalOperations()).isEqualTo(1);
        assertThat(metricsRecorder.snapshot().successfulOperations()).isEqualTo(1);
        assertThat(metricsRecorder.snapshot().retryAttempts()).isEqualTo(1);
        assertThat(auditRecorder.recorded().getFirst().outcome()).isEqualTo(FhirAuditOutcome.FAILURE);
        assertThat(auditRecorder.recorded().getLast().outcome()).isEqualTo(FhirAuditOutcome.SUCCESS);
    }

    @Test
    void repeatedInfrastructureFailuresOpenTheCircuitThenFailFast() {
        AtomicInteger fhirCalls = new AtomicInteger();
        stubRead(invocation -> {
            fhirCalls.incrementAndGet();
            throw new FhirClientConnectionException("connection refused");
        });
        RoutingService routing = routing();
        for (int i = 0; i < 3; i++) {
            assertThatThrownBy(() -> routing.readPatient(
                            RoutingRequest.readPatient("local-hapi", "patient-001", "pipe-open")))
                    .isInstanceOf(FhirClientException.class);
        }

        assertThat(circuitBreakers.forDestination("local-hapi").state()).isEqualTo(CircuitBreakerState.OPEN);
        assertThat(fhirCalls.get()).isEqualTo(9);

        assertThatThrownBy(() -> routing.readPatient(
                        RoutingRequest.readPatient("local-hapi", "patient-001", "pipe-cb-block")))
                .isInstanceOf(CircuitBreakerOpenException.class);

        assertThat(fhirCalls.get()).isEqualTo(9);
        assertThat(auditRecorder.recorded().getLast().error()).isEqualTo(FhirErrorCategory.CIRCUIT_OPEN);
        assertThat(metricsRecorder.snapshot().retryAttempts()).isEqualTo(6);
    }

    private void stubRead(org.mockito.stubbing.Answer<Patient> answer) {
        when(fhirClient.read().resource(Patient.class).withId("patient-001").execute()).thenAnswer(answer);
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
                FhirRetryExecutor.of(properties.retryPolicy(), FhirSleeper.noop()),
                circuitBreakers,
                rateLimiters,
                bulkheads);
    }

    private static Patient patient() {
        Patient patient = new Patient();
        patient.setId("patient-001");
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
