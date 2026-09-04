package lab.healthcare.fhir.routing;

import lab.healthcare.fhir.auth.AccessTokenProvider;
import lab.healthcare.fhir.capability.FhirCapabilityDiscoveryService;
import lab.healthcare.fhir.capability.FhirCapabilityException;
import lab.healthcare.fhir.capability.FhirServerCapabilities;
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
import org.hl7.fhir.r4.model.Bundle;
import org.hl7.fhir.r4.model.Patient;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.UUID;
import java.util.concurrent.TimeUnit;
import java.util.function.Function;

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
    private final FhirCapabilityDiscoveryService capabilityDiscovery;

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
        this.capabilityDiscovery = new FhirCapabilityDiscoveryService();
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
        requireRequest(request);
        return clientFor(request.destination());
    }

    public Patient readPatient(RoutingRequest request) {
        requireRequest(request);
        FhirOperationContext context = context(request);
        long started = System.nanoTime();
        String logicalId;
        try {
            logicalId = patientLogicalId(request);
        } catch (RuntimeException ex) {
            observe(failure(context, elapsedMs(started), ex, 1, false), true);
            throw ex;
        }
        return executeAgainstDestination(
                request.destination(),
                context,
                started,
                fhirClient -> new FhirService(fhirClient).readPatient(logicalId));
    }

    public FhirServerCapabilities discoverCapabilities(String destination) {
        return discoverCapabilities(destination, null);
    }

    public FhirServerCapabilities discoverCapabilities(String destination, String correlationId) {
        if (destination == null || destination.isBlank()) {
            throw new IllegalArgumentException("Destination must be provided");
        }
        String name = destination.trim();
        return executeAgainstDestination(
                name,
                null,
                discoveryContext(name, correlationId),
                System.nanoTime(),
                fhirClient -> capabilityDiscovery.discover(name, fhirClient));
    }

    public Patient readPatient(String destination, AccessTokenProvider tokenProvider, String patientId) {
        return readPatient(destination, tokenProvider, patientId, null);
    }

    public Patient readPatient(
            String destination, AccessTokenProvider tokenProvider, String patientId, String correlationId) {
        if (destination == null || destination.isBlank()) {
            throw new IllegalArgumentException("Destination must be provided");
        }
        if (tokenProvider == null) {
            throw new IllegalArgumentException("Access token provider must be provided");
        }
        if (patientId == null || patientId.isBlank()) {
            throw new IllegalArgumentException("Patient logical ID must be provided");
        }
        String dest = destination.trim();
        String logicalId = patientId.trim();
        return executeAgainstDestination(
                dest,
                tokenProvider,
                authenticatedReadContext(dest, logicalId, correlationId),
                System.nanoTime(),
                fhirClient -> new FhirService(fhirClient).readPatient(logicalId));
    }

    public Bundle searchConditions(String destination, AccessTokenProvider tokenProvider, String patientId) {
        return searchConditions(destination, tokenProvider, patientId, null);
    }

    public Bundle searchConditions(
            String destination, AccessTokenProvider tokenProvider, String patientId, String correlationId) {
        if (destination == null || destination.isBlank()) {
            throw new IllegalArgumentException("Destination must be provided");
        }
        if (tokenProvider == null) {
            throw new IllegalArgumentException("Access token provider must be provided");
        }
        if (patientId == null || patientId.isBlank()) {
            throw new IllegalArgumentException("Patient logical ID must be provided");
        }
        String dest = destination.trim();
        String logicalId = patientId.trim();
        return executeAgainstDestination(
                dest,
                tokenProvider,
                conditionSearchContext(dest, correlationId),
                System.nanoTime(),
                fhirClient -> new FhirService(fhirClient)
                        .searchConditionsByPatientWithCount(logicalId, 5, "problem-list-item"));
    }

    public Bundle searchObservations(String destination, AccessTokenProvider tokenProvider, String patientId) {
        return searchObservations(destination, tokenProvider, patientId, null);
    }

    public Bundle searchObservations(
            String destination, AccessTokenProvider tokenProvider, String patientId, String correlationId) {
        if (destination == null || destination.isBlank()) {
            throw new IllegalArgumentException("Destination must be provided");
        }
        if (tokenProvider == null) {
            throw new IllegalArgumentException("Access token provider must be provided");
        }
        if (patientId == null || patientId.isBlank()) {
            throw new IllegalArgumentException("Patient logical ID must be provided");
        }
        String dest = destination.trim();
        String logicalId = patientId.trim();
        return executeAgainstDestination(
                dest,
                tokenProvider,
                observationSearchContext(dest, correlationId),
                System.nanoTime(),
                fhirClient -> new FhirService(fhirClient).searchObservationsByPatientWithCount(logicalId, 5));
    }

    public Bundle searchPatients(String destination, AccessTokenProvider tokenProvider, String patientName) {
        return searchPatients(destination, tokenProvider, patientName, null);
    }

    public Bundle searchPatients(
            String destination, AccessTokenProvider tokenProvider, String patientName, String correlationId) {
        if (destination == null || destination.isBlank()) {
            throw new IllegalArgumentException("Destination must be provided");
        }
        if (tokenProvider == null) {
            throw new IllegalArgumentException("Access token provider must be provided");
        }
        if (patientName == null || patientName.isBlank()) {
            throw new IllegalArgumentException("Patient name search parameter must be provided");
        }
        String dest = destination.trim();
        String name = patientName.trim();
        return executeAgainstDestination(
                dest,
                tokenProvider,
                searchContext(dest, correlationId),
                System.nanoTime(),
                fhirClient -> new FhirService(fhirClient).searchPatientsByNameWithCount(name, 1));
    }

    private IGenericClient clientFor(String destination) {
        return clientFor(destination, null);
    }

    private IGenericClient clientFor(String destination, AccessTokenProvider override) {
        try {
            FhirServerProfile profile = registry.enabledProfile(destination);
            AccessTokenProvider tokenProvider = override != null ? override : tokenProviders.forProfile(profile);
            FhirContext fhirContext = clientFactory.createContext(profile);
            return clientFactory.createClient(fhirContext, profile, tokenProvider);
        } catch (IllegalStateException | IllegalArgumentException ex) {
            throw RoutingException.fromRegistry(destination, ex);
        }
    }

    private <T> T executeAgainstDestination(
            String destination,
            FhirOperationContext context,
            long started,
            Function<IGenericClient, T> operation) {
        return executeAgainstDestination(destination, null, context, started, operation);
    }

    private <T> T executeAgainstDestination(
            String destination,
            AccessTokenProvider tokenProvider,
            FhirOperationContext context,
            long started,
            Function<IGenericClient, T> operation) {
        IGenericClient fhirClient;
        try {
            fhirClient = clientFor(destination, tokenProvider);
            rateLimiters.forDestination(destination).acquire();
        } catch (RuntimeException ex) {
            observe(failure(context, elapsedMs(started), ex, 1, false), true);
            throw ex;
        }
        FhirCircuitBreaker breaker = circuitBreakers.forDestination(destination);
        try {
            return bulkheads.forDestination(destination).execute(() -> {
                try {
                    breaker.acquire();
                } catch (CircuitBreakerOpenException ex) {
                    observe(failure(context, elapsedMs(started), ex, 1, false), true);
                    throw ex;
                }
                try {
                    T result = retryExecutor.execute(
                            () -> operation.apply(fhirClient),
                            attempt -> observeAttempt(context, attempt));
                    breaker.recordSuccess();
                    return result;
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

    private static FhirOperationContext authenticatedReadContext(
            String destination, String logicalId, String correlationId) {
        String id = correlationId == null || correlationId.isBlank()
                ? UUID.randomUUID().toString()
                : correlationId.trim();
        return new FhirOperationContext(id, destination, FhirAuditOperation.READ, "Patient", logicalId);
    }

    private static FhirOperationContext conditionSearchContext(String destination, String correlationId) {
        String id = correlationId == null || correlationId.isBlank()
                ? UUID.randomUUID().toString()
                : correlationId.trim();
        return new FhirOperationContext(
                id,
                destination,
                FhirAuditOperation.CONDITION_SEARCH,
                "Condition",
                null);
    }

    private static FhirOperationContext observationSearchContext(String destination, String correlationId) {
        String id = correlationId == null || correlationId.isBlank()
                ? UUID.randomUUID().toString()
                : correlationId.trim();
        return new FhirOperationContext(
                id,
                destination,
                FhirAuditOperation.OBSERVATION_SEARCH,
                "Observation",
                null);
    }

    private static FhirOperationContext searchContext(String destination, String correlationId) {
        String id = correlationId == null || correlationId.isBlank()
                ? UUID.randomUUID().toString()
                : correlationId.trim();
        return new FhirOperationContext(
                id,
                destination,
                FhirAuditOperation.PATIENT_SEARCH,
                "Patient",
                null);
    }

    private static FhirOperationContext discoveryContext(String destination, String correlationId) {
        String id = correlationId == null || correlationId.isBlank()
                ? UUID.randomUUID().toString()
                : correlationId.trim();
        return new FhirOperationContext(
                id,
                destination,
                FhirAuditOperation.CAPABILITY_DISCOVERY,
                "CapabilityStatement",
                null);
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
        if (ex instanceof FhirCapabilityException capability) {
            return new FhirErrorDetails(
                    FhirErrorCategory.VALIDATION_ERROR,
                    null,
                    FhirAuditOperation.CAPABILITY_DISCOVERY.name(),
                    null,
                    "CapabilityStatement",
                    null,
                    capability.getMessage());
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
