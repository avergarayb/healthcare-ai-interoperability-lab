package lab.healthcare.fhir.aiconsumerenforcement;

/**
 * Clinical data-access enforcement verdict. Never includes tokens,
 * Patient identifiers, or FHIR JSON. A synthetic enforcement claim is
 * not a grant and is not a FHIR read.
 */
public record AiConsumerClinicalDataEnforcementResult(
        String boundaryVersion,
        AiConsumerClinicalDataEnforcementStatus status,
        String reason,
        String operation,
        boolean inputAvailable,
        String requestSource,
        boolean accessRequestReferencePresent,
        boolean authorizationDecisionReferencePresent,
        String enforcementEvaluationStatus,
        String decisionReason,
        boolean enforcementDecisionAvailable,
        boolean enforcementDecisionEvaluated,
        boolean realAuthorizationRequired,
        boolean clinicalDataAccessGranted,
        boolean clinicalDataAccessAllowed,
        boolean clinicalDataAccessEnforcementAvailable,
        boolean clinicalDataAccessEnforced,
        boolean clinicalDataAccessEnforcementProviderConfigured,
        boolean clinicalDataAccessEnforcementExecuted,
        boolean accessRequestEvaluated,
        boolean clinicalDataAccessRequested,
        boolean clinicalDataAccessGrantAvailable,
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
    public static final String EVALUATION_NOT_EVALUATED = "NOT_EVALUATED";

    static AiConsumerClinicalDataEnforcementResult denied(
            AiConsumerClinicalDataEnforcementStatus status,
            String reason,
            boolean inputAvailable,
            String requestSource,
            boolean accessRequestReferencePresent,
            boolean authorizationDecisionReferencePresent) {
        return new AiConsumerClinicalDataEnforcementResult(
                VERSION_V1,
                status,
                reason,
                AiConsumerClinicalDataEnforcementOperations.EVALUATE_CLINICAL_DATA_ENFORCEMENT,
                inputAvailable,
                requestSource,
                accessRequestReferencePresent,
                authorizationDecisionReferencePresent,
                EVALUATION_NOT_EVALUATED,
                reason,
                false,
                false,
                true,
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
                false,
                false,
                false,
                false,
                false,
                NOT_EXECUTED,
                NOT_DISPATCHED,
                true);
    }

    public AiConsumerClinicalDataEnforcementResult {
        if (status == null) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement status must be provided");
        }
        if (enforcementDecisionAvailable) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement has no decision");
        }
        if (enforcementDecisionEvaluated) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement must not evaluate a decision");
        }
        if (!realAuthorizationRequired) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement requires real authorization");
        }
        if (clinicalDataAccessGranted) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement must not grant clinical access");
        }
        if (clinicalDataAccessAllowed) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement must not allow clinical data access");
        }
        if (clinicalDataAccessEnforcementAvailable) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement is not available");
        }
        if (clinicalDataAccessEnforced) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement must not enforce access");
        }
        if (clinicalDataAccessEnforcementProviderConfigured) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement has no provider");
        }
        if (clinicalDataAccessEnforcementExecuted) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement must not execute enforcement");
        }
        if (accessRequestEvaluated) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement must not evaluate a request");
        }
        if (clinicalDataAccessRequested) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement must not request clinical access");
        }
        if (clinicalDataAccessGrantAvailable) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement grant is not available");
        }
        if (clinicalDataAccessProviderConfigured) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement has no access provider");
        }
        if (clinicalDataAccessAuthorizationAvailable) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement has no authorization");
        }
        if (scopeEvaluated) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement must not evaluate a scope");
        }
        if (minimizationEvaluated) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement must not evaluate minimization");
        }
        if (purposeScopeAlignmentEvaluated) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement must not evaluate purpose-scope alignment");
        }
        if (clinicalDataScopeProviderConfigured) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement has no scope provider");
        }
        if (clinicalDataScopeApprovalAvailable) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement approval is not available");
        }
        if (consentVerified) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement must not verify consent");
        }
        if (purposeApproved) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement must not approve a purpose");
        }
        if (dataScopeApproved) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement must not approve a data scope");
        }
        if (consentProviderConfigured) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement has no consent provider");
        }
        if (consentAvailable) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement has no consent");
        }
        if (authenticationVerified) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement must not verify authentication");
        }
        if (authorizationGranted) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement must not grant authorization");
        }
        if (realSecurityProviderConfigured) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement has no real security provider");
        }
        if (consumerAuthorizationAvailable) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement has no consumer authorization");
        }
        if (handoffAuthorized) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement must not authorize handoff");
        }
        if (dispatchPerformed) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement must not perform dispatch");
        }
        if (externalAuthorizationAvailable) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement has no external authorization");
        }
        if (modelCallAuthorized) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement must not authorize a model call");
        }
        if (modelCalled) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement must not call a model");
        }
        if (!NOT_EXECUTED.equals(blankToEmpty(processingStatus))) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement must not execute model processing");
        }
        if (!NOT_DISPATCHED.equals(blankToEmpty(dispatchStatus))) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement must not dispatch");
        }
        if (!requiresHumanReview) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement requires human review");
        }
        boundaryVersion = VERSION_V1;
        reason = blankToEmpty(reason);
        operation = blankToEmpty(operation);
        requestSource = blankToEmpty(requestSource);
        enforcementEvaluationStatus = EVALUATION_NOT_EVALUATED;
        decisionReason = blankToEmpty(decisionReason);
        processingStatus = NOT_EXECUTED;
        dispatchStatus = NOT_DISPATCHED;
    }

    private static String blankToEmpty(String value) {
        return value == null ? "" : value.trim();
    }
}
