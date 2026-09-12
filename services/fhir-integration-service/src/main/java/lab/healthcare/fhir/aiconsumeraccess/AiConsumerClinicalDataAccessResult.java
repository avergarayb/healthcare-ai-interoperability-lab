package lab.healthcare.fhir.aiconsumeraccess;

import java.util.List;

/**
 * Clinical data-access request verdict. Never includes tokens, Patient
 * identifiers, or FHIR JSON. A declared or even effective synthetic
 * request is not a grant and is not a FHIR read.
 */
public record AiConsumerClinicalDataAccessResult(
        String boundaryVersion,
        AiConsumerClinicalDataAccessStatus status,
        String reason,
        String operation,
        boolean inputAvailable,
        String requestSource,
        List<String> requestedDataCategories,
        List<String> requestedResourceTypes,
        String requestedTenantScope,
        String requestEvaluationStatus,
        String enforcementStatus,
        String decisionReason,
        boolean accessRequestDeclared,
        boolean accessRequestEvaluated,
        boolean scopeReferencePresent,
        boolean realAuthorizationRequired,
        boolean clinicalDataAccessRequested,
        boolean clinicalDataAccessGranted,
        boolean clinicalDataAccessAllowed,
        boolean clinicalDataAccessGrantAvailable,
        boolean clinicalDataAccessEnforced,
        boolean clinicalDataAccessProviderConfigured,
        boolean clinicalDataAccessAuthorizationAvailable,
        boolean scopeEvaluated,
        boolean minimizationEvaluated,
        boolean purposeScopeAlignmentEvaluated,
        boolean clinicalDataScopeProviderConfigured,
        boolean clinicalDataScopeApprovalAvailable,
        boolean consentVerified,
        boolean purposeApproved,
        boolean dataScopeApproved,
        boolean consentProviderConfigured,
        boolean consentAvailable,
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
    public static final String VERSION_V1 = "v1";
    public static final String REQUEST_NOT_EVALUATED = "NOT_EVALUATED";
    public static final String NOT_ENFORCED = "NOT_ENFORCED";

    static AiConsumerClinicalDataAccessResult denied(
            AiConsumerClinicalDataAccessStatus status,
            String reason,
            boolean inputAvailable,
            String requestSource,
            List<String> requestedDataCategories,
            List<String> requestedResourceTypes,
            String requestedTenantScope,
            boolean accessRequestDeclared,
            boolean scopeReferencePresent,
            boolean clinicalDataAccessRequested) {
        return new AiConsumerClinicalDataAccessResult(
                VERSION_V1,
                status,
                reason,
                AiConsumerClinicalDataAccessOperations.EVALUATE_CLINICAL_DATA_ACCESS_REQUEST,
                inputAvailable,
                requestSource,
                requestedDataCategories,
                requestedResourceTypes,
                requestedTenantScope,
                REQUEST_NOT_EVALUATED,
                NOT_ENFORCED,
                reason,
                accessRequestDeclared,
                false,
                scopeReferencePresent,
                true,
                clinicalDataAccessRequested,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                NOT_EXECUTED,
                NOT_DISPATCHED,
                true);
    }

    public AiConsumerClinicalDataAccessResult {
        if (status == null) {
            throw new IllegalArgumentException("AI consumer clinical data-access status must be provided");
        }
        if (accessRequestEvaluated) {
            throw new IllegalArgumentException("AI consumer clinical data-access must not evaluate a request");
        }
        if (clinicalDataAccessGranted) {
            throw new IllegalArgumentException("AI consumer clinical data-access must not grant clinical access");
        }
        if (clinicalDataAccessAllowed) {
            throw new IllegalArgumentException("AI consumer clinical data-access must not allow clinical data access");
        }
        if (clinicalDataAccessGrantAvailable) {
            throw new IllegalArgumentException("AI consumer clinical data-access grant is not available");
        }
        if (clinicalDataAccessEnforced) {
            throw new IllegalArgumentException("AI consumer clinical data-access must not enforce access");
        }
        if (clinicalDataAccessProviderConfigured) {
            throw new IllegalArgumentException("AI consumer clinical data-access has no access provider");
        }
        if (clinicalDataAccessAuthorizationAvailable) {
            throw new IllegalArgumentException("AI consumer clinical data-access has no authorization");
        }
        if (!realAuthorizationRequired) {
            throw new IllegalArgumentException("AI consumer clinical data-access requires real authorization");
        }
        if (scopeEvaluated) {
            throw new IllegalArgumentException("AI consumer clinical data-access must not evaluate a scope");
        }
        if (minimizationEvaluated) {
            throw new IllegalArgumentException("AI consumer clinical data-access must not evaluate minimization");
        }
        if (purposeScopeAlignmentEvaluated) {
            throw new IllegalArgumentException("AI consumer clinical data-access must not evaluate purpose-scope alignment");
        }
        if (clinicalDataScopeProviderConfigured) {
            throw new IllegalArgumentException("AI consumer clinical data-access has no scope provider");
        }
        if (clinicalDataScopeApprovalAvailable) {
            throw new IllegalArgumentException("AI consumer clinical data-access approval is not available");
        }
        if (consentVerified) {
            throw new IllegalArgumentException("AI consumer clinical data-access must not verify consent");
        }
        if (purposeApproved) {
            throw new IllegalArgumentException("AI consumer clinical data-access must not approve a purpose");
        }
        if (dataScopeApproved) {
            throw new IllegalArgumentException("AI consumer clinical data-access must not approve a data scope");
        }
        if (consentProviderConfigured) {
            throw new IllegalArgumentException("AI consumer clinical data-access has no consent provider");
        }
        if (consentAvailable) {
            throw new IllegalArgumentException("AI consumer clinical data-access has no consent");
        }
        if (authenticationVerified) {
            throw new IllegalArgumentException("AI consumer clinical data-access must not verify authentication");
        }
        if (authorizationGranted) {
            throw new IllegalArgumentException("AI consumer clinical data-access must not grant authorization");
        }
        if (realSecurityProviderConfigured) {
            throw new IllegalArgumentException("AI consumer clinical data-access has no real security provider");
        }
        if (consumerAuthorizationAvailable) {
            throw new IllegalArgumentException("AI consumer clinical data-access has no consumer authorization");
        }
        if (handoffAuthorized) {
            throw new IllegalArgumentException("AI consumer clinical data-access must not authorize handoff");
        }
        if (dispatchPerformed) {
            throw new IllegalArgumentException("AI consumer clinical data-access must not perform dispatch");
        }
        if (externalAuthorizationAvailable) {
            throw new IllegalArgumentException("AI consumer clinical data-access has no external authorization");
        }
        if (modelCallAuthorized) {
            throw new IllegalArgumentException("AI consumer clinical data-access must not authorize a model call");
        }
        if (modelCalled) {
            throw new IllegalArgumentException("AI consumer clinical data-access must not call a model");
        }
        if (!NOT_EXECUTED.equals(blankToEmpty(processingStatus))) {
            throw new IllegalArgumentException("AI consumer clinical data-access must not execute model processing");
        }
        if (!NOT_DISPATCHED.equals(blankToEmpty(dispatchStatus))) {
            throw new IllegalArgumentException("AI consumer clinical data-access must not dispatch");
        }
        if (!requiresHumanReview) {
            throw new IllegalArgumentException("AI consumer clinical data-access requires human review");
        }
        boundaryVersion = VERSION_V1;
        reason = blankToEmpty(reason);
        operation = blankToEmpty(operation);
        requestSource = blankToEmpty(requestSource);
        requestedTenantScope = blankToEmpty(requestedTenantScope);
        requestEvaluationStatus = REQUEST_NOT_EVALUATED;
        enforcementStatus = NOT_ENFORCED;
        decisionReason = blankToEmpty(decisionReason);
        requestedDataCategories = requestedDataCategories == null ? List.of() : List.copyOf(requestedDataCategories);
        requestedResourceTypes = requestedResourceTypes == null ? List.of() : List.copyOf(requestedResourceTypes);
        processingStatus = NOT_EXECUTED;
        dispatchStatus = NOT_DISPATCHED;
    }

    private static String blankToEmpty(String value) {
        return value == null ? "" : value.trim();
    }
}
