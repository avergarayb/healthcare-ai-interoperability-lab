package lab.healthcare.fhir.federation.audit;

import java.time.Clock;
import java.time.Instant;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;
import java.util.regex.Pattern;

/** Builds and persists the closed event contract for Clinical Federation. */
public final class FederationSecurityAudit {

    private static final Pattern TRUSTED_CORRELATION = Pattern.compile("FED-[A-F0-9]{16}");

    private final FederationSecurityAuditRecorder recorder;
    private final Clock clock;

    public FederationSecurityAudit(FederationSecurityAuditRecorder recorder) {
        this(recorder, Clock.systemUTC());
    }

    public FederationSecurityAudit(FederationSecurityAuditRecorder recorder, Clock clock) {
        if (recorder == null || clock == null) {
            throw new IllegalArgumentException("Federation security audit dependencies are required");
        }
        this.recorder = recorder;
        this.clock = clock;
    }

    public String correlationId(String candidate) {
        if (candidate != null && TRUSTED_CORRELATION.matcher(candidate).matches()) {
            return candidate;
        }
        return "FED-" + UUID.randomUUID().toString()
                .replace("-", "")
                .substring(0, 16)
                .toUpperCase(Locale.ROOT);
    }

    public FederationSecurityAuditEvent authenticationDenied(String reasonCode) {
        return append("anonymous", "anonymous", null, "denied", reasonCode, correlationId(null));
    }

    public FederationSecurityAuditEvent authorizationDenied(
            String actorId, String organizationId, String reasonCode, String correlationId) {
        return append(
                "federation_participant",
                actorId,
                organizationId,
                "denied",
                reasonCode,
                correlationId(correlationId));
    }

    public FederationSecurityAuditEvent allowed(
            String actorId, String organizationId, String correlationId) {
        return append(
                "federation_participant",
                actorId,
                organizationId,
                "allowed",
                "access_granted",
                correlationId(correlationId));
    }

    private FederationSecurityAuditEvent append(
            String actorType,
            String actorId,
            String organizationId,
            String outcome,
            String reasonCode,
            String correlationId) {
        FederationSecurityAuditEvent event = new FederationSecurityAuditEvent(
                UUID.randomUUID().toString(),
                Instant.now(clock),
                FederationSecurityAuditEvent.EVENT_TYPE,
                FederationSecurityAuditEvent.SOURCE_SERVICE,
                actorType,
                actorId,
                organizationId,
                FederationSecurityAuditEvent.ACTION,
                FederationSecurityAuditEvent.RESOURCE_TYPE,
                FederationSecurityAuditEvent.RESOURCE_REFERENCE,
                outcome,
                reasonCode,
                correlationId,
                Map.of("route", FederationSecurityAuditEvent.ROUTE),
                FederationSecurityAuditEvent.CONTRACT_VERSION);
        try {
            recorder.append(event);
        } catch (FederationSecurityAuditUnavailable ex) {
            throw ex;
        } catch (RuntimeException ex) {
            throw new FederationSecurityAuditUnavailable(ex);
        }
        return event;
    }
}
