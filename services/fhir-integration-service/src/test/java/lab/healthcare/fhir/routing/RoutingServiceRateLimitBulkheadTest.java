package lab.healthcare.fhir.routing;

import lab.healthcare.fhir.auth.oauth2.OAuth2TokenClient;
import lab.healthcare.fhir.client.FhirAccessTokenProviders;
import lab.healthcare.fhir.client.FhirClientFactory;
import lab.healthcare.fhir.exception.FhirErrorCategory;
import lab.healthcare.fhir.observability.FhirAuditOutcome;
import lab.healthcare.fhir.observability.InMemoryFhirMetricsRecorder;
import lab.healthcare.fhir.observability.LoggingFhirAuditRecorder;
import lab.healthcare.fhir.resilience.CircuitBreakerState;
import lab.healthcare.fhir.resilience.FhirCircuitBreakerRegistry;
import lab.healthcare.fhir.resilience.FhirRetryExecutor;
import lab.healthcare.fhir.resilience.MutableClock;
import lab.healthcare.fhir.resilience.bulkhead.BulkheadFullException;
import lab.healthcare.fhir.resilience.bulkhead.FhirBulkheadPolicy;
import lab.healthcare.fhir.resilience.bulkhead.FhirBulkheadRegistry;
import lab.healthcare.fhir.resilience.ratelimit.FhirRateLimiterPolicy;
import lab.healthcare.fhir.resilience.ratelimit.FhirRateLimiterRegistry;
import lab.healthcare.fhir.resilience.ratelimit.RateLimitExceededException;
import lab.healthcare.fhir.server.FhirServerProfile;
import lab.healthcare.fhir.server.FhirServerProfileRegistry;
import lab.healthcare.fhir.server.FhirServersProperties;
import lab.healthcare.fhir.smart.AuthorizationCodeClient;
import lab.healthcare.fhir.smart.SmartConfigurationClient;

import ca.uhn.fhir.context.FhirContext;
import ca.uhn.fhir.rest.client.api.IGenericClient;
import org.hl7.fhir.r4.model.Patient;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Answers;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.Clock;
import java.time.Duration;
import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class RoutingServiceRateLimitBulkheadTest {

    private final LoggingFhirAuditRecorder auditRecorder = new LoggingFhirAuditRecorder();
    private final InMemoryFhirMetricsRecorder metricsRecorder = new InMemoryFhirMetricsRecorder();
    private final FhirCircuitBreakerRegistry circuitBreakers = new FhirCircuitBreakerRegistry();
    private final MutableClock clock = MutableClock.epoch();

    @Mock
    private FhirClientFactory mockFactory;

    @Mock(answer = Answers.RETURNS_DEEP_STUBS)
    private IGenericClient fhirClient;

    @Test
    void eleventhLogicalReadIsRateLimitedBeforeFhirRetryAndCircuit() {
        AtomicInteger fhirCalls = new AtomicInteger();
        stubSuccessfulRead(fhirCalls);
        FhirRateLimiterRegistry rateLimiters = FhirRateLimiterRegistry.of(
                FhirRateLimiterPolicy.defaults(), clock);
        RoutingService routing = routing(rateLimiters, new FhirBulkheadRegistry());

        for (int i = 0; i < 10; i++) {
            routing.readPatient(RoutingRequest.readPatient("local-hapi", "patient-001", "rl-ok"));
        }
        assertThatThrownBy(() -> routing.readPatient(
                        RoutingRequest.readPatient("local-hapi", "patient-001", "rl-blocked")))
                .isInstanceOf(RateLimitExceededException.class)
                .hasMessage(FhirErrorCategory.RATE_LIMITED.safeMessage());

        assertThat(fhirCalls.get()).isEqualTo(10);
        assertThat(circuitBreakers.forDestination("local-hapi").state()).isEqualTo(CircuitBreakerState.CLOSED);
        assertThat(auditRecorder.recorded().getLast().error()).isEqualTo(FhirErrorCategory.RATE_LIMITED);
        assertThat(auditRecorder.recorded().getLast().outcome()).isEqualTo(FhirAuditOutcome.FAILURE);
        assertThat(auditRecorder.recorded().getLast().willRetry()).isFalse();
        assertThat(auditRecorder.recorded().getLast().toLogLine()).contains("error=RATE_LIMITED");
        assertThat(auditRecorder.recorded().getLast().toLogLine()).doesNotContain("access_token");
        assertThat(metricsRecorder.snapshot().totalOperations()).isEqualTo(11);
        assertThat(metricsRecorder.snapshot().failedOperations()).isEqualTo(1);
        assertThat(metricsRecorder.snapshot().retryAttempts()).isZero();
    }

    @Test
    void exhaustedBulkheadRejectsBeforeFhirRetryAndCircuit() {
        AtomicInteger fhirCalls = new AtomicInteger();
        FhirBulkheadRegistry bulkheads = FhirBulkheadRegistry.of(FhirBulkheadPolicy.defaults());
        for (int i = 0; i < 5; i++) {
            bulkheads.forDestination("local-hapi").acquire();
        }
        RoutingService routing = routing(new FhirRateLimiterRegistry(), bulkheads);

        assertThatThrownBy(() -> routing.readPatient(
                        RoutingRequest.readPatient("local-hapi", "patient-001", "bh-blocked")))
                .isInstanceOf(BulkheadFullException.class)
                .hasMessage(FhirErrorCategory.BULKHEAD_FULL.safeMessage());

        assertThat(fhirCalls.get()).isZero();
        assertThat(circuitBreakers.forDestination("local-hapi").state()).isEqualTo(CircuitBreakerState.CLOSED);
        assertThat(auditRecorder.recorded().getLast().error()).isEqualTo(FhirErrorCategory.BULKHEAD_FULL);
        assertThat(auditRecorder.recorded().getLast().willRetry()).isFalse();
        assertThat(metricsRecorder.snapshot().totalOperations()).isEqualTo(1);
        assertThat(metricsRecorder.snapshot().failedOperations()).isEqualTo(1);
        assertThat(metricsRecorder.snapshot().retryAttempts()).isZero();
    }

    @Test
    void newRateWindowAllowsTrafficAgain() {
        AtomicInteger fhirCalls = new AtomicInteger();
        stubSuccessfulRead(fhirCalls);
        FhirRateLimiterRegistry rateLimiters = FhirRateLimiterRegistry.of(
                new FhirRateLimiterPolicy(1, Duration.ofSeconds(1)), clock);
        RoutingService routing = routing(rateLimiters, new FhirBulkheadRegistry());

        routing.readPatient(RoutingRequest.readPatient("local-hapi", "patient-001", "rl-first"));
        assertThatThrownBy(() -> routing.readPatient(
                        RoutingRequest.readPatient("local-hapi", "patient-001", "rl-same-window")))
                .isInstanceOf(RateLimitExceededException.class);
        clock.advance(Duration.ofSeconds(1));
        routing.readPatient(RoutingRequest.readPatient("local-hapi", "patient-001", "rl-next-window"));

        assertThat(fhirCalls.get()).isEqualTo(2);
        assertThat(circuitBreakers.forDestination("local-hapi").state()).isEqualTo(CircuitBreakerState.CLOSED);
    }

    private void stubSuccessfulRead(AtomicInteger fhirCalls) {
        Patient patient = new Patient();
        patient.setId("patient-001");
        when(fhirClient.read().resource(Patient.class).withId("patient-001").execute())
                .thenAnswer(invocation -> {
                    fhirCalls.incrementAndGet();
                    return patient;
                });
    }

    private RoutingService routing(FhirRateLimiterRegistry rateLimiters, FhirBulkheadRegistry bulkheads) {
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
                circuitBreakers,
                rateLimiters,
                bulkheads);
    }

    private static FhirServersProperties servers() {
        return new FhirServersProperties(
                "local-hapi",
                Map.of("local-hapi", new FhirServersProperties.ServerSettings(
                        "http://localhost:8080/fhir", "R4", true, null)));
    }
}
