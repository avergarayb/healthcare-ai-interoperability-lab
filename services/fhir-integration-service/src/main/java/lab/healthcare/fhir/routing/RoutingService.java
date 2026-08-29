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
import lab.healthcare.fhir.resilience.FhirRetryAttempt;
import lab.healthcare.fhir.resilience.FhirRetryExecutor;
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

    public RoutingService(
            FhirServerProfileRegistry registry,
            FhirClientFactory clientFactory,
            FhirAccessTokenProviders tokenProviders,
            FhirAuditRecorder auditRecorder,
            FhirMetricsRecorder metricsRecorder,
            FhirRetryExecutor retryExecutor) {
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
        this.registry = registry;
        this.clientFactory = clientFactory;
        this.tokenProviders = tokenProviders;
        this.auditRecorder = auditRecorder;
        this.metricsRecorder = metricsRecorder;
        this.retryExecutor = retryExecutor;
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
        } catch (RuntimeException ex) {
            observe(failure(context, elapsedMs(started), ex, 1, false), true);
            throw ex;
        }
        return retryExecutor.execute(
                () -> new FhirService(fhirClient).readPatient(logicalId),
                attempt -> observeAttempt(context, attempt));
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
