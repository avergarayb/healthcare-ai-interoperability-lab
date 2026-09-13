package lab.healthcare.fhir.aiconsumerenforcementverificationapproval;

/**
 * Synthetic enforcement verification-approval verdict. Never includes
 * tokens, Patient identifiers, or FHIR JSON. A verification decision
 * is not an approval and an approval is not a clinical grant.
 */
public record AiConsumerEnforcementVerificationApprovalResult(
        String boundaryVersion,
        AiConsumerEnforcementVerificationApprovalStatus status,
        String reason,
        String operation,
        boolean inputAvailable,
        String requestSource,
        String approvalEvaluationStatus,
        String decisionReason,
        boolean verificationApprovalAvailable,
        boolean verificationApprovalEvaluated,
        boolean approvalEvidenceEvaluated,
        boolean approvalPolicyEvaluated,
        boolean approvalHumanReviewRequired,
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

    static AiConsumerEnforcementVerificationApprovalResult denied(
            AiConsumerEnforcementVerificationApprovalStatus status,
            String reason,
            boolean inputAvailable,
            String requestSource) {
        return new AiConsumerEnforcementVerificationApprovalResult(
                VERSION_V1,
                status,
                reason,
                AiConsumerEnforcementVerificationApprovalOperations.EVALUATE_ENFORCEMENT_VERIFICATION_APPROVAL,
                inputAvailable,
                requestSource,
                EVALUATION_NOT_EVALUATED,
                reason,
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

    public AiConsumerEnforcementVerificationApprovalResult {
        if (status == null) {
            throw new IllegalArgumentException(
                    "AI consumer enforcement verification-approval status must be provided");
        }
        if (verificationApprovalAvailable) {
            throw new IllegalArgumentException("AI consumer verification approval is not available");
        }
        if (verificationApprovalEvaluated) {
            throw new IllegalArgumentException("AI consumer verification approval must not be evaluated");
        }
        if (approvalEvidenceEvaluated) {
            throw new IllegalArgumentException("AI consumer verification approval must not evaluate evidence");
        }
        if (approvalPolicyEvaluated) {
            throw new IllegalArgumentException("AI consumer verification approval must not evaluate policy");
        }
        if (!approvalHumanReviewRequired) {
            throw new IllegalArgumentException("AI consumer verification approval requires human review");
        }
        if (verificationApproved) {
            throw new IllegalArgumentException("AI consumer verification approval must not approve verification");
        }
        if (executionVerified) {
            throw new IllegalArgumentException("AI consumer verification approval must not treat claimed verification as approval");
        }
        if (clinicalDataAccessGranted) {
            throw new IllegalArgumentException("AI consumer verification approval must not grant clinical access");
        }
        if (clinicalDataAccessAllowed) {
            throw new IllegalArgumentException("AI consumer verification approval must not allow clinical data access");
        }
        if (clinicalDataAccessRequested) {
            throw new IllegalArgumentException("AI consumer verification approval must not request clinical access");
        }
        if (clinicalDataAccessEnforced) {
            throw new IllegalArgumentException("AI consumer verification approval must not enforce access");
        }
        if (enforcementExecutionPerformed) {
            throw new IllegalArgumentException("AI consumer verification approval must not treat claimed execution as evidence");
        }
        if (decisionAvailable
                || decisionEvaluated
                || verificationInputAccepted
                || verificationEvidenceAccepted
                || verificationDecisionProviderConfigured
                || verificationDecisionAvailable
                || verificationDecisionEvaluated
                || executionEvidenceAvailable
                || executionEvidenceEvaluated
                || executionVerificationAvailable
                || executionVerificationProviderConfigured
                || executionDecisionAvailable
                || executionDecisionEvaluated
                || enforcementExecutionAvailable
                || enforcementExecutionProviderConfigured
                || !realAuthorizationRequired
                || enforcementDecisionAvailable
                || enforcementDecisionEvaluated
                || clinicalDataAccessEnforcementAvailable
                || clinicalDataAccessEnforcementProviderConfigured
                || clinicalDataAccessEnforcementExecuted
                || accessRequestEvaluated
                || clinicalDataAccessGrantAvailable
                || clinicalDataAccessProviderConfigured
                || clinicalDataAccessAuthorizationAvailable
                || scopeEvaluated
                || minimizationEvaluated
                || purposeScopeAlignmentEvaluated
                || clinicalDataScopeProviderConfigured
                || clinicalDataScopeApprovalAvailable
                || consentVerified
                || purposeApproved
                || dataScopeApproved
                || consentProviderConfigured
                || consentAvailable
                || authenticationVerified
                || authorizationGranted
                || realSecurityProviderConfigured
                || consumerAuthorizationAvailable
                || handoffAuthorized
                || dispatchPerformed
                || externalAuthorizationAvailable
                || modelCallAuthorized
                || modelCalled) {
            throw new IllegalArgumentException("AI consumer verification approval must preserve deny-by-default invariants");
        }
        if (!NOT_EXECUTED.equals(blankToEmpty(processingStatus))) {
            throw new IllegalArgumentException("AI consumer verification approval must not execute model processing");
        }
        if (!NOT_DISPATCHED.equals(blankToEmpty(dispatchStatus))) {
            throw new IllegalArgumentException("AI consumer verification approval must not dispatch");
        }
        if (!requiresHumanReview) {
            throw new IllegalArgumentException("AI consumer verification approval requires human review");
        }
        boundaryVersion = VERSION_V1;
        reason = blankToEmpty(reason);
        operation = blankToEmpty(operation);
        requestSource = blankToEmpty(requestSource);
        approvalEvaluationStatus = EVALUATION_NOT_EVALUATED;
        decisionReason = blankToEmpty(decisionReason);
        processingStatus = NOT_EXECUTED;
        dispatchStatus = NOT_DISPATCHED;
    }

    private static String blankToEmpty(String value) {
        return value == null ? "" : value.trim();
    }
}
