package lab.healthcare.fhir.aiconsumerauthorization;

/**
 * Consumer authentication and authorization verdict. Never includes tokens,
 * Patient identifiers, or FHIR JSON. A declared identity is not authentication
 * and is not handoff permission.
 */
public record AiConsumerAuthorizationResult(
        AiConsumerAuthorizationStatus status,
        String reason,
        String operation,
        String requestedScope,
        boolean authenticationVerified,
        boolean authorizationGranted,
        boolean realSecurityProviderConfigured,
        boolean consumerAuthorizationAvailable,
        boolean handoffAuthorized,
        boolean dispatchPerformed,
        boolean externalAuthorizationAvailable,
        boolean modelCallAuthorized,
        boolean modelCalled,
        String processingStatus,
        String dispatchStatus,
        boolean requiresHumanReview) {

    public static final String NOT_EXECUTED = "NOT_EXECUTED";
    public static final String NOT_DISPATCHED = "NOT_DISPATCHED";
    public static final String NOT_AUTHENTICATED = "NOT_AUTHENTICATED";

    public AiConsumerAuthorizationResult {
        if (status == null) {
            throw new IllegalArgumentException("AI consumer authorization status must be provided");
        }
        if (authenticationVerified) {
            throw new IllegalArgumentException("AI consumer authorization must not verify authentication");
        }
        if (authorizationGranted) {
            throw new IllegalArgumentException("AI consumer authorization must not grant authorization");
        }
        if (realSecurityProviderConfigured) {
            throw new IllegalArgumentException("AI consumer authorization has no real security provider");
        }
        if (consumerAuthorizationAvailable) {
            throw new IllegalArgumentException("AI consumer authorization is not available");
        }
        if (handoffAuthorized) {
            throw new IllegalArgumentException("AI consumer authorization must not authorize handoff");
        }
        if (dispatchPerformed) {
            throw new IllegalArgumentException("AI consumer authorization must not perform dispatch");
        }
        if (externalAuthorizationAvailable) {
            throw new IllegalArgumentException("AI consumer authorization has no external authorization");
        }
        if (modelCallAuthorized) {
            throw new IllegalArgumentException("AI consumer authorization must not authorize a model call");
        }
        if (modelCalled) {
            throw new IllegalArgumentException("AI consumer authorization must not call a model");
        }
        if (!NOT_EXECUTED.equals(blankToEmpty(processingStatus))) {
            throw new IllegalArgumentException("AI consumer authorization must not execute model processing");
        }
        if (!NOT_DISPATCHED.equals(blankToEmpty(dispatchStatus))) {
            throw new IllegalArgumentException("AI consumer authorization must not dispatch");
        }
        if (!requiresHumanReview) {
            throw new IllegalArgumentException("AI consumer authorization requires human review");
        }
        reason = blankToEmpty(reason);
        operation = blankToEmpty(operation);
        requestedScope = blankToEmpty(requestedScope);
        processingStatus = NOT_EXECUTED;
        dispatchStatus = NOT_DISPATCHED;
    }

    public String authenticationDisplay() {
        return NOT_AUTHENTICATED;
    }

    @Override
    public String toString() {
        return "AiConsumerAuthorizationResult[status="
                + status
                + ", reason="
                + reason
                + ", operation="
                + operation
                + ", requestedScope="
                + requestedScope
                + ", authenticationVerified="
                + authenticationVerified
                + ", authorizationGranted="
                + authorizationGranted
                + ", realSecurityProviderConfigured="
                + realSecurityProviderConfigured
                + ", consumerAuthorizationAvailable="
                + consumerAuthorizationAvailable
                + ", handoffAuthorized="
                + handoffAuthorized
                + ", dispatchPerformed="
                + dispatchPerformed
                + ", externalAuthorizationAvailable="
                + externalAuthorizationAvailable
                + ", modelCallAuthorized="
                + modelCallAuthorized
                + ", modelCalled="
                + modelCalled
                + ", processingStatus="
                + processingStatus
                + ", dispatchStatus="
                + dispatchStatus
                + ", requiresHumanReview="
                + requiresHumanReview
                + "]";
    }

    private static String blankToEmpty(String value) {
        return value == null ? "" : value.trim();
    }
}
