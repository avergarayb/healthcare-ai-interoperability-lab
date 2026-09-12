package lab.healthcare.fhir.aiconsumerconsent;

/**
 * Consent and purpose verdict. Never includes tokens, Patient identifiers,
 * signatures, or FHIR JSON. A declared purpose is not approval and is not
 * clinical access.
 */
public record AiConsumerConsentResult(
        AiConsumerConsentStatus status,
        String reason,
        String operation,
        String requestedPurpose,
        String requestedDataScope,
        boolean consentVerified,
        boolean purposeApproved,
        boolean dataScopeApproved,
        boolean consentProviderConfigured,
        boolean consentAvailable,
        boolean clinicalDataAccessAllowed,
        boolean humanReviewCompleted,
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
    public static final String PURPOSE_NOT_VERIFIED = "PURPOSE_NOT_VERIFIED";
    public static final String DATA_SCOPE_NOT_VERIFIED = "DATA_SCOPE_NOT_VERIFIED";

    public AiConsumerConsentResult {
        if (status == null) {
            throw new IllegalArgumentException("AI consumer consent status must be provided");
        }
        if (consentVerified) {
            throw new IllegalArgumentException("AI consumer consent must not verify consent");
        }
        if (purposeApproved) {
            throw new IllegalArgumentException("AI consumer consent must not approve a purpose");
        }
        if (dataScopeApproved) {
            throw new IllegalArgumentException("AI consumer consent must not approve a data scope");
        }
        if (consentProviderConfigured) {
            throw new IllegalArgumentException("AI consumer consent has no consent provider");
        }
        if (consentAvailable) {
            throw new IllegalArgumentException("AI consumer consent is not available");
        }
        if (clinicalDataAccessAllowed) {
            throw new IllegalArgumentException("AI consumer consent must not allow clinical data access");
        }
        if (humanReviewCompleted) {
            throw new IllegalArgumentException("AI consumer consent must not complete human review");
        }
        if (authenticationVerified) {
            throw new IllegalArgumentException("AI consumer consent must not verify authentication");
        }
        if (authorizationGranted) {
            throw new IllegalArgumentException("AI consumer consent must not grant authorization");
        }
        if (realSecurityProviderConfigured) {
            throw new IllegalArgumentException("AI consumer consent has no real security provider");
        }
        if (consumerAuthorizationAvailable) {
            throw new IllegalArgumentException("AI consumer consent has no consumer authorization");
        }
        if (handoffAuthorized) {
            throw new IllegalArgumentException("AI consumer consent must not authorize handoff");
        }
        if (dispatchPerformed) {
            throw new IllegalArgumentException("AI consumer consent must not perform dispatch");
        }
        if (externalAuthorizationAvailable) {
            throw new IllegalArgumentException("AI consumer consent has no external authorization");
        }
        if (modelCallAuthorized) {
            throw new IllegalArgumentException("AI consumer consent must not authorize a model call");
        }
        if (modelCalled) {
            throw new IllegalArgumentException("AI consumer consent must not call a model");
        }
        if (!NOT_EXECUTED.equals(blankToEmpty(processingStatus))) {
            throw new IllegalArgumentException("AI consumer consent must not execute model processing");
        }
        if (!NOT_DISPATCHED.equals(blankToEmpty(dispatchStatus))) {
            throw new IllegalArgumentException("AI consumer consent must not dispatch");
        }
        if (!requiresHumanReview) {
            throw new IllegalArgumentException("AI consumer consent requires human review");
        }
        reason = blankToEmpty(reason);
        operation = blankToEmpty(operation);
        requestedPurpose = blankToEmpty(requestedPurpose);
        requestedDataScope = blankToEmpty(requestedDataScope);
        processingStatus = NOT_EXECUTED;
        dispatchStatus = NOT_DISPATCHED;
    }

    public String purposeDisplay() {
        return PURPOSE_NOT_VERIFIED;
    }

    public String dataScopeDisplay() {
        return DATA_SCOPE_NOT_VERIFIED;
    }

    @Override
    public String toString() {
        return "AiConsumerConsentResult[status="
                + status
                + ", reason="
                + reason
                + ", operation="
                + operation
                + ", requestedPurpose="
                + requestedPurpose
                + ", requestedDataScope="
                + requestedDataScope
                + ", consentVerified="
                + consentVerified
                + ", purposeApproved="
                + purposeApproved
                + ", dataScopeApproved="
                + dataScopeApproved
                + ", consentProviderConfigured="
                + consentProviderConfigured
                + ", consentAvailable="
                + consentAvailable
                + ", clinicalDataAccessAllowed="
                + clinicalDataAccessAllowed
                + ", humanReviewCompleted="
                + humanReviewCompleted
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
