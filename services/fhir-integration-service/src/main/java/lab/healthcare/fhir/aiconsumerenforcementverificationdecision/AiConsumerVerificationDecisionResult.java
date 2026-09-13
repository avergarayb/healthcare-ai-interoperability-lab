package lab.healthcare.fhir.aiconsumerenforcementverificationdecision;

/**
 * Clinical data-access enforcement verification-decision verdict.
 * Never includes tokens, Patient identifiers, or FHIR JSON. A
 * verification result is not a decision and a decision is not a grant.
 */
public record AiConsumerVerificationDecisionResult(
        String boundaryVersion,
        AiConsumerVerificationDecisionStatus status,
        String reason,
        String operation,
        boolean inputAvailable,
        String requestSource,
        String decisionEvaluationStatus,
        String decisionReason,
        boolean decisionAvailable,
        boolean decisionEvaluated,
        boolean verificationInputAccepted,
        boolean verificationEvidenceAccepted,
        boolean verificationDecisionProviderConfigured,
        boolean verificationApproved,
        boolean verificationDecisionAvailable,
        boolean verificationDecisionEvaluated,
        boolean executionEvidenceAvailable,
        boolean executionEvidenceEvaluated,
        boolean executionVerificationAvailable,
        boolean executionVerificationProviderConfigured,
        boolean executionVerified,
        boolean executionDecisionAvailable,
        boolean executionDecisionEvaluated,
        boolean enforcementExecutionAvailable,
        boolean enforcementExecutionProviderConfigured,
        boolean enforcementExecutionPerformed,
        boolean realAuthorizationRequired,
        boolean clinicalDataAccessGranted,
        boolean clinicalDataAccessAllowed,
        boolean clinicalDataAccessEnforced,
        boolean enforcementDecisionAvailable,
        boolean enforcementDecisionEvaluated,
        boolean clinicalDataAccessEnforcementAvailable,
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

    static AiConsumerVerificationDecisionResult denied(
            AiConsumerVerificationDecisionStatus status,
            String reason,
            boolean inputAvailable,
            String requestSource) {
        return new AiConsumerVerificationDecisionResult(
                VERSION_V1,
                status,
                reason,
                AiConsumerVerificationDecisionOperations
                        .EVALUATE_CLINICAL_DATA_ENFORCEMENT_VERIFICATION_DECISION,
                inputAvailable,
                requestSource,
                EVALUATION_NOT_EVALUATED,
                reason,
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
                false,
                false,
                NOT_EXECUTED,
                NOT_DISPATCHED,
                true);
    }

    public AiConsumerVerificationDecisionResult {
        if (status == null) {
            throw new IllegalArgumentException(
                    "AI consumer clinical data-enforcement verification decision status must be provided");
        }
        if (decisionAvailable) {
            throw new IllegalArgumentException("AI consumer verification decision is not available");
        }
        if (decisionEvaluated) {
            throw new IllegalArgumentException("AI consumer verification decision must not be evaluated");
        }
        if (verificationInputAccepted) {
            throw new IllegalArgumentException("AI consumer verification decision must not accept input");
        }
        if (verificationEvidenceAccepted) {
            throw new IllegalArgumentException("AI consumer verification decision must not accept evidence");
        }
        if (verificationDecisionProviderConfigured) {
            throw new IllegalArgumentException("AI consumer verification decision has no provider");
        }
        if (verificationApproved) {
            throw new IllegalArgumentException("AI consumer verification decision must not approve verification");
        }
        if (verificationDecisionAvailable) {
            throw new IllegalArgumentException("AI consumer verification has no decision");
        }
        if (verificationDecisionEvaluated) {
            throw new IllegalArgumentException("AI consumer verification must not evaluate a decision");
        }
        if (executionEvidenceAvailable) {
            throw new IllegalArgumentException("AI consumer verification decision has no execution evidence");
        }
        if (executionEvidenceEvaluated) {
            throw new IllegalArgumentException("AI consumer verification decision must not evaluate evidence");
        }
        if (executionVerificationAvailable) {
            throw new IllegalArgumentException("AI consumer verification is not available");
        }
        if (executionVerificationProviderConfigured) {
            throw new IllegalArgumentException("AI consumer verification has no provider");
        }
        if (executionVerified) {
            throw new IllegalArgumentException("AI consumer verification decision must not treat claimed verification as approval");
        }
        if (executionDecisionAvailable) {
            throw new IllegalArgumentException("AI consumer verification decision has no execution decision");
        }
        if (executionDecisionEvaluated) {
            throw new IllegalArgumentException("AI consumer verification decision must not evaluate execution");
        }
        if (enforcementExecutionAvailable) {
            throw new IllegalArgumentException("AI consumer verification decision has no execution");
        }
        if (enforcementExecutionProviderConfigured) {
            throw new IllegalArgumentException("AI consumer verification decision has no execution provider");
        }
        if (enforcementExecutionPerformed) {
            throw new IllegalArgumentException("AI consumer verification decision must not treat claimed execution as evidence");
        }
        if (!realAuthorizationRequired) {
            throw new IllegalArgumentException("AI consumer verification decision requires real authorization");
        }
        if (clinicalDataAccessGranted) {
            throw new IllegalArgumentException("AI consumer verification decision must not grant clinical access");
        }
        if (clinicalDataAccessAllowed) {
            throw new IllegalArgumentException("AI consumer verification decision must not allow clinical data access");
        }
        if (clinicalDataAccessEnforced) {
            throw new IllegalArgumentException("AI consumer verification decision must not enforce access");
        }
        if (enforcementDecisionAvailable) {
            throw new IllegalArgumentException("AI consumer verification decision has no enforcement decision");
        }
        if (enforcementDecisionEvaluated) {
            throw new IllegalArgumentException("AI consumer verification decision must not evaluate enforcement");
        }
        if (clinicalDataAccessEnforcementAvailable) {
            throw new IllegalArgumentException("AI consumer verification decision has no enforcement");
        }
        if (clinicalDataAccessEnforcementProviderConfigured) {
            throw new IllegalArgumentException("AI consumer verification decision has no enforcement provider");
        }
        if (clinicalDataAccessEnforcementExecuted) {
            throw new IllegalArgumentException("AI consumer verification decision must not execute enforcement");
        }
        if (accessRequestEvaluated) {
            throw new IllegalArgumentException("AI consumer verification decision must not evaluate a request");
        }
        if (clinicalDataAccessRequested) {
            throw new IllegalArgumentException("AI consumer verification decision must not request clinical access");
        }
        if (clinicalDataAccessGrantAvailable) {
            throw new IllegalArgumentException("AI consumer verification decision grant is not available");
        }
        if (clinicalDataAccessProviderConfigured) {
            throw new IllegalArgumentException("AI consumer verification decision has no access provider");
        }
        if (clinicalDataAccessAuthorizationAvailable) {
            throw new IllegalArgumentException("AI consumer verification decision has no authorization");
        }
        if (scopeEvaluated) {
            throw new IllegalArgumentException("AI consumer verification decision must not evaluate a scope");
        }
        if (minimizationEvaluated) {
            throw new IllegalArgumentException("AI consumer verification decision must not evaluate minimization");
        }
        if (purposeScopeAlignmentEvaluated) {
            throw new IllegalArgumentException("AI consumer verification decision must not evaluate purpose-scope alignment");
        }
        if (clinicalDataScopeProviderConfigured) {
            throw new IllegalArgumentException("AI consumer verification decision has no scope provider");
        }
        if (clinicalDataScopeApprovalAvailable) {
            throw new IllegalArgumentException("AI consumer verification decision approval is not available");
        }
        if (consentVerified) {
            throw new IllegalArgumentException("AI consumer verification decision must not verify consent");
        }
        if (purposeApproved) {
            throw new IllegalArgumentException("AI consumer verification decision must not approve a purpose");
        }
        if (dataScopeApproved) {
            throw new IllegalArgumentException("AI consumer verification decision must not approve a data scope");
        }
        if (consentProviderConfigured) {
            throw new IllegalArgumentException("AI consumer verification decision has no consent provider");
        }
        if (consentAvailable) {
            throw new IllegalArgumentException("AI consumer verification decision has no consent");
        }
        if (authenticationVerified) {
            throw new IllegalArgumentException("AI consumer verification decision must not verify authentication");
        }
        if (authorizationGranted) {
            throw new IllegalArgumentException("AI consumer verification decision must not grant authorization");
        }
        if (realSecurityProviderConfigured) {
            throw new IllegalArgumentException("AI consumer verification decision has no real security provider");
        }
        if (consumerAuthorizationAvailable) {
            throw new IllegalArgumentException("AI consumer verification decision has no consumer authorization");
        }
        if (handoffAuthorized) {
            throw new IllegalArgumentException("AI consumer verification decision must not authorize handoff");
        }
        if (dispatchPerformed) {
            throw new IllegalArgumentException("AI consumer verification decision must not perform dispatch");
        }
        if (externalAuthorizationAvailable) {
            throw new IllegalArgumentException("AI consumer verification decision has no external authorization");
        }
        if (modelCallAuthorized) {
            throw new IllegalArgumentException("AI consumer verification decision must not authorize a model call");
        }
        if (modelCalled) {
            throw new IllegalArgumentException("AI consumer verification decision must not call a model");
        }
        if (!NOT_EXECUTED.equals(blankToEmpty(processingStatus))) {
            throw new IllegalArgumentException("AI consumer verification decision must not execute model processing");
        }
        if (!NOT_DISPATCHED.equals(blankToEmpty(dispatchStatus))) {
            throw new IllegalArgumentException("AI consumer verification decision must not dispatch");
        }
        if (!requiresHumanReview) {
            throw new IllegalArgumentException("AI consumer verification decision requires human review");
        }
        boundaryVersion = VERSION_V1;
        reason = blankToEmpty(reason);
        operation = blankToEmpty(operation);
        requestSource = blankToEmpty(requestSource);
        decisionEvaluationStatus = EVALUATION_NOT_EVALUATED;
        decisionReason = blankToEmpty(decisionReason);
        processingStatus = NOT_EXECUTED;
        dispatchStatus = NOT_DISPATCHED;
    }

    private static String blankToEmpty(String value) {
        return value == null ? "" : value.trim();
    }
}
