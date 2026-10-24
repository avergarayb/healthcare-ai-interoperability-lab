package lab.healthcare.fhir.federation.audit;

import java.time.Instant;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.regex.Pattern;

/**
 * Minimized access decision for the Clinical Federation HTTP boundary.
 * This event is not a FHIR resource and does not describe query completion.
 */
public record FederationSecurityAuditEvent(
        String eventId,
        Instant timestampUtc,
        String eventType,
        String sourceService,
        String actorType,
        String actorId,
        String organizationId,
        String action,
        String resourceType,
        String resourceReference,
        String outcome,
        String reasonCode,
        String correlationId,
        Map<String, String> metadata,
        String contractVersion) {

    public static final String EVENT_TYPE = "clinical_federation_access";
    public static final String SOURCE_SERVICE = "fhir-integration-service";
    public static final String ACTION = "read_federated_context";
    public static final String RESOURCE_TYPE = "clinical_federation_context";
    public static final String RESOURCE_REFERENCE = "clinical-federation/context";
    public static final String ROUTE = "/api/clinical-federation/v1/context";
    public static final String CONTRACT_VERSION = "security-audit-v1";

    private static final Pattern SAFE_ID = Pattern.compile("[A-Za-z0-9.-]{1,64}");
    private static final Pattern CORRELATION = Pattern.compile("FED-[A-F0-9]{16}");
    private static final Set<String> AUTHENTICATION_REASONS = Set.of(
            "participant_token_missing",
            "participant_token_invalid",
            "participant_authentication_unconfigured",
            "participant_not_authenticated");
    private static final Set<String> AUTHORIZATION_REASONS = Set.of(
            "participant_not_registered",
            "organization_not_authorized",
            "caller_system_not_authorized",
            "source_not_granted");

    public FederationSecurityAuditEvent {
        requireUuidV4(eventId);
        if (timestampUtc == null) {
            throw new IllegalArgumentException("timestamp_utc is required");
        }
        require(EVENT_TYPE.equals(eventType), "event_type is invalid");
        require(SOURCE_SERVICE.equals(sourceService), "source_service is invalid");
        require(ACTION.equals(action), "action is invalid");
        require(RESOURCE_TYPE.equals(resourceType), "resource_type is invalid");
        require(RESOURCE_REFERENCE.equals(resourceReference), "resource_reference is invalid");
        require(CONTRACT_VERSION.equals(contractVersion), "contract_version is invalid");
        require(CORRELATION.matcher(correlationId == null ? "" : correlationId).matches(),
                "correlation_id is invalid");
        require(metadata != null && metadata.equals(Map.of("route", ROUTE)), "metadata is invalid");
        metadata = Map.copyOf(metadata);

        if ("allowed".equals(outcome)) {
            require("federation_participant".equals(actorType), "allowed actor_type is invalid");
            requireSafeId(actorId, "actor_id");
            requireSafeId(organizationId, "organization_id");
            require("access_granted".equals(reasonCode), "allowed reason_code is invalid");
        } else if ("denied".equals(outcome)) {
            if (AUTHENTICATION_REASONS.contains(reasonCode)) {
                require("anonymous".equals(actorType) && "anonymous".equals(actorId),
                        "authentication denial actor is invalid");
                require(organizationId == null, "authentication denial organization is invalid");
            } else if (AUTHORIZATION_REASONS.contains(reasonCode)) {
                require("federation_participant".equals(actorType),
                        "authorization denial actor_type is invalid");
                requireSafeId(actorId, "actor_id");
                if ("participant_not_registered".equals(reasonCode)) {
                    require(organizationId == null, "unregistered participant organization is invalid");
                } else {
                    requireSafeId(organizationId, "organization_id");
                }
            } else {
                throw new IllegalArgumentException("denied reason_code is invalid");
            }
        } else {
            throw new IllegalArgumentException("outcome is invalid");
        }
    }

    private static void requireUuidV4(String value) {
        try {
            UUID parsed = UUID.fromString(value);
            require(parsed.version() == 4 && parsed.toString().equals(value), "event_id is invalid");
        } catch (IllegalArgumentException | NullPointerException ex) {
            throw new IllegalArgumentException("event_id is invalid");
        }
    }

    private static void requireSafeId(String value, String field) {
        require(value != null && SAFE_ID.matcher(value).matches(), field + " is invalid");
    }

    private static void require(boolean condition, String message) {
        if (!condition) {
            throw new IllegalArgumentException(message);
        }
    }
}
