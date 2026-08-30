package lab.healthcare.fhir.routing;

import lab.healthcare.fhir.auth.AccessTokenProvider;
import lab.healthcare.fhir.client.FhirAccessTokenProviders;
import lab.healthcare.fhir.client.FhirClientFactory;
import lab.healthcare.fhir.client.FhirService;
import lab.healthcare.fhir.exception.FhirClientException;
import lab.healthcare.fhir.exception.FhirErrorCategory;
import lab.healthcare.fhir.exception.FhirErrorClassifier;
import lab.healthcare.fhir.exception.FhirErrorDetails;
import lab.healthcare.fhir.observability.FhirAuditEvent;
import lab.healthcare.fhir.observability.FhirAuditOperation;
import lab.healthcare.fhir.observability.FhirAuditOutcome;
import lab.healthcare.fhir.observability.FhirAuditRecorder;
import lab.healthcare.fhir.observability.FhirMetricsRecorder;
import lab.healthcare.fhir.observability.FhirOperationContext;
import lab.healthcare.fhir.resilience.CircuitBreakerOpenException;
import lab.healthcare.fhir.resilience.FhirCircuitBreaker;
import lab.healthcare.fhir.resilience.FhirCircuitBreakerRegistry;
import lab.healthcare.fhir.resilience.FhirRetryAttempt;
import lab.healthcare.fhir.resilience.FhirRetryExecutor;
import lab.healthcare.fhir.resilience.bulkhead.BulkheadFullException;
import lab.healthcare.fhir.resilience.bulkhead.FhirBulkheadRegistry;
import lab.healthcare.fhir.resilience.ratelimit.FhirRateLimiterRegistry;
import lab.healthcare.fhir.resilience.ratelimit.RateLimitExceededException;
import lab.healthcare.fhir.server.FhirServerProfile;
import lab.healthcare.fhir.server.FhirServerProfileRegistry;

import ca.uhn.fhir.context.FhirContext;
import ca.uhn.fhir.rest.client.api.IGenericClient;
import org.hl7.fhir.r4.model.Patient;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.UUID;
import java.util.concurrent.TimeUnit;

@Service
public class RoutingService {

    private final FhirServerProfileRegistry registry;
    private final FhirClientFactory clientFactory;
    private final FhirAccessTokenProviders tokenProviders;
    private final FhirAuditRecorder auditRecorder;
    private final FhirMetricsRecorder metricsRecorder;
    private final FhirRetryExecutor retryExecutor;
    private final FhirCircuitBreakerRegistry circuitBreakers;
    private final FhirRateLimiterRegistry rateLimiters;
    private final FhirBulkheadRegistry bulkheads;

    public RoutingService(
            FhirServerProfileRegistry registry,
            FhirClientFactory clientFactory,
            FhirAccessTokenProviders tokenProviders,
            FhirAuditRecorder auditRecorder,
            FhirMetricsRecorder metricsRecorder,
            FhirRetryExecutor retryExecutor,
            FhirCircuitBreakerRegistry circuitBreakers,
            FhirRateLimiterRegistry rateLimiters,
            FhirBulkheadRegistry bulkheads) {
        if (registry == null) {
            throw new IllegalArgumentException("FHIR server profile registry must be provided");
        }
        if (clientFactory == null) {
            throw new IllegalArgumentException("FHIR client factory must be provided");
        }
        if (tokenProviders == null) {
            throw new IllegalArgumentException("Access token providers must be provided");
        }
        if (auditRecorder == null) {
            throw new IllegalArgumentException("Audit recorder must be provided");
        }
        if (metricsRecorder == null) {
            throw new IllegalArgumentException("Metrics recorder must be provided");
        }
        if (retryExecutor == null) {
            throw new IllegalArgumentException("Retry executor must be provided");
        }
        if (circuitBreakers == null) {
            throw new IllegalArgumentException("Circuit breaker registry must be provided");
        }
        if (rateLimiters == null) {
            throw new IllegalArgumentException("Rate limiter registry must be provided");
        }
        if (bulkheads == null) {
            throw new IllegalArgumentException("Bulkhead registry must be provided");
        }
        this.registry = registry;
        this.clientFactory = clientFactory;
        this.tokenProviders = tokenProviders;
        this.auditRecorder = auditRecorder;
        this.metricsRecorder = metricsRecorder;
        this.retryExecutor = retryExecutor;
        this.circuitBreakers = circuitBreakers;
        this.rateLimiters = rateLimiters;
        this.bulkheads = bulkheads;
    }

    public FhirServerProfile resolve(RoutingRequest request) {
        requireRequest(request);
        try {
            return registry.enabledProfile(request.destination());
        } catch (IllegalStateException | IllegalArgumentException ex) {
            throw RoutingException.fromRegistry(request.destination(), ex);
        }
    }

    public IGenericClient client(RoutingRequest request) {
        FhirServerProfile profile = resolve(request);
        AccessTokenProvider tokenProvider = tokenProviders.forProfile(profile);
        FhirContext fhirContext = clientFactory.createContext(profile);
        return clientFactory.createClient(fhirContext, profile, tokenProvider);
    }

    public Patient readPatient(RoutingRequest request) {
        requireRequest(request);
        FhirOperationContext context = context(request);
        String logicalId;
        IGenericClient fhirClient;
        long started = System.nanoTime();
        try {
            logicalId = patientLogicalId(request);
            fhirClient = client(request);
            rateLimiters.forDestination(request.destination()).acquire();
        } catch (RuntimeException ex) {
            observe(failure(context, elapsedMs(started), ex, 1, false), true);
            throw ex;
        }
        FhirCircuitBreaker breaker = circuitBreakers.forDestination(request.destination());
        try {
            return bulkheads.forDestination(request.destination()).execute(() -> {
                try {
                    breaker.acquire();
                } catch (CircuitBreakerOpenException ex) {
                    observe(failure(context, elapsedMs(started), ex, 1, false), true);
                    throw ex;
                }
                try {
                    Patient patient = retryExecutor.execute(
                            () -> new FhirService(fhirClient).readPatient(logicalId),
                            attempt -> observeAttempt(context, attempt));
                    breaker.recordSuccess();
                    return patient;
                } catch (RuntimeException ex) {
                    breaker.recordFailure(ex);
                    throw ex;
                }
            });
        } catch (BulkheadFullException ex) {
            observe(failure(context, elapsedMs(started), ex, 1, false), true);
            throw ex;
        }
    }

    private static String patientLogicalId(RoutingRequest request) {
        if (!(request.resource() instanceof Patient patient)) {
            throw new RoutingException(invalidRequest(request.destination(), "FHIR routing request is invalid: Patient resource required"));
        }
        String logicalId = patient.getIdElement().getIdPart();
        if (logicalId == null || logicalId.isBlank()) {
            throw new RoutingException(invalidRequest(request.destination(), "FHIR routing request is invalid: Patient logical ID must be provided"));
        }
        return logicalId;
    }

    private void observeAttempt(FhirOperationContext context, FhirRetryAttempt attempt) {
        FhirAuditEvent event = attempt.success()
                ? success(context, attempt.durationMs(), attempt.attempt())
                : failure(context, attempt.durationMs(), attempt.error(), attempt.attempt(), attempt.willRetry());
        observe(event, attempt.success() || !attempt.willRetry());
    }

    private void observe(FhirAuditEvent event, boolean logicalOutcome) {
        auditRecorder.record(event);
        if (logicalOutcome) {
            metricsRecorder.record(event);
        }
    }

    private static FhirOperationContext context(RoutingRequest request) {
        String correlationId = request.correlationId() == null
                ? UUID.randomUUID().toString()
                : request.correlationId();
        String resourceId = request.resource().getIdElement().getIdPart();
        return new FhirOperationContext(
                correlationId,
                request.destination(),
                FhirAuditOperation.READ,
                request.resource().fhirType(),
                resourceId);
    }

    private static FhirAuditEvent success(FhirOperationContext context, long durationMs, int attempt) {
        return new FhirAuditEvent(
                Instant.now(),
                context,
                FhirAuditOutcome.SUCCESS,
                200,
                durationMs,
                null,
                attempt,
                false);
    }

    private static FhirAuditEvent failure(
            FhirOperationContext context,
            long durationMs,
            RuntimeException ex,
            int attempt,
            boolean willRetry) {
        FhirErrorDetails details = detailsOf(ex);
        return new FhirAuditEvent(
                Instant.now(),
                context,
                FhirAuditOutcome.FAILURE,
                details.status(),
                durationMs,
                details.category(),
                attempt,
                willRetry);
    }

    private static long elapsedMs(long startedNanos) {
        return TimeUnit.NANOSECONDS.toMillis(Math.max(0L, System.nanoTime() - startedNanos));
    }

    private static FhirErrorDetails detailsOf(RuntimeException ex) {
        if (ex instanceof RateLimitExceededException limited) {
            return limited.details();
        }
        if (ex instanceof BulkheadFullException full) {
            return full.details();
        }
        if (ex instanceof CircuitBreakerOpenException open) {
            return open.details();
        }
        if (ex instanceof RoutingException routing) {
            return routing.details();
        }
        if (ex instanceof FhirClientException fhir) {
            return fhir.details();
        }
        return FhirErrorClassifier.classify(ex);
    }

    private static FhirErrorDetails invalidRequest(String destination, String message) {
        return new FhirErrorDetails(
                FhirErrorCategory.VALIDATION_ERROR, null, FhirAuditOperation.READ.name(), destination, null, null, message);
    }

    private static void requireRequest(RoutingRequest request) {
        if (request == null) {
            throw new IllegalArgumentException("Routing request must be provided");
        }
    }
}
