package lab.healthcare.fhir.routing;

import lab.healthcare.fhir.auth.AccessTokenProvider;
import lab.healthcare.fhir.client.FhirAccessTokenProviders;
import lab.healthcare.fhir.client.FhirClientFactory;
import lab.healthcare.fhir.client.FhirService;
import lab.healthcare.fhir.exception.FhirClientException;
import lab.healthcare.fhir.observability.FhirAuditError;
import lab.healthcare.fhir.observability.FhirAuditEvent;
import lab.healthcare.fhir.observability.FhirAuditOperation;
import lab.healthcare.fhir.observability.FhirAuditOutcome;
import lab.healthcare.fhir.observability.FhirAuditRecorder;
import lab.healthcare.fhir.observability.FhirOperationContext;
import lab.healthcare.fhir.server.FhirServerProfile;
import lab.healthcare.fhir.server.FhirServerProfileRegistry;

import ca.uhn.fhir.context.FhirContext;
import ca.uhn.fhir.rest.client.api.IGenericClient;
import ca.uhn.fhir.rest.server.exceptions.BaseServerResponseException;
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

    public RoutingService(
            FhirServerProfileRegistry registry,
            FhirClientFactory clientFactory,
            FhirAccessTokenProviders tokenProviders,
            FhirAuditRecorder auditRecorder) {
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
        this.registry = registry;
        this.clientFactory = clientFactory;
        this.tokenProviders = tokenProviders;
        this.auditRecorder = auditRecorder;
    }

    public FhirServerProfile resolve(RoutingRequest request) {
        requireRequest(request);
        try {
            return registry.enabledProfile(request.destination());
        } catch (IllegalStateException | IllegalArgumentException ex) {
            throw new RoutingException(ex.getMessage(), ex);
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
        long started = System.nanoTime();
        try {
            String logicalId = patientLogicalId(request);
            Patient patient = new FhirService(client(request)).readPatient(logicalId);
            auditRecorder.record(success(context, started, 200));
            return patient;
        } catch (RuntimeException ex) {
            auditRecorder.record(failure(context, started, ex));
            throw ex;
        }
    }

    private static String patientLogicalId(RoutingRequest request) {
        if (!(request.resource() instanceof Patient patient)) {
            throw new RoutingException("Routing request resource must be a Patient");
        }
        String logicalId = patient.getIdElement().getIdPart();
        if (logicalId == null || logicalId.isBlank()) {
            throw new RoutingException("Patient logical ID must be provided");
        }
        return logicalId;
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

    private static FhirAuditEvent success(FhirOperationContext context, long startedNanos, int status) {
        return new FhirAuditEvent(
                Instant.now(),
                context,
                FhirAuditOutcome.SUCCESS,
                status,
                elapsedMs(startedNanos),
                null);
    }

    private static FhirAuditEvent failure(FhirOperationContext context, long startedNanos, RuntimeException ex) {
        return new FhirAuditEvent(
                Instant.now(),
                context,
                FhirAuditOutcome.FAILURE,
                fhirStatus(ex),
                elapsedMs(startedNanos),
                errorCategory(ex));
    }

    private static long elapsedMs(long startedNanos) {
        return TimeUnit.NANOSECONDS.toMillis(Math.max(0L, System.nanoTime() - startedNanos));
    }

    private static Integer fhirStatus(RuntimeException ex) {
        Throwable cause = ex.getCause();
        if (cause instanceof BaseServerResponseException fhir) {
            return fhir.getStatusCode();
        }
        return null;
    }

    private static FhirAuditError errorCategory(RuntimeException ex) {
        if (ex instanceof RoutingException) {
            String message = ex.getMessage() == null ? "" : ex.getMessage();
            if (message.contains("Unknown FHIR server profile")) {
                return FhirAuditError.DESTINATION_NOT_FOUND;
            }
            if (message.contains("disabled")) {
                return FhirAuditError.DESTINATION_DISABLED;
            }
            return FhirAuditError.INVALID_REQUEST;
        }
        if (ex instanceof FhirClientException) {
            Integer status = fhirStatus(ex);
            if (status != null && status == 404) {
                return FhirAuditError.RESOURCE_NOT_FOUND;
            }
            return FhirAuditError.FHIR_ERROR;
        }
        return FhirAuditError.FHIR_ERROR;
    }

    private static void requireRequest(RoutingRequest request) {
        if (request == null) {
            throw new IllegalArgumentException("Routing request must be provided");
        }
    }
}
