package lab.healthcare.fhir.aiconsumerenforcementverificationapproval;

import lab.healthcare.fhir.aiconsumerenforcementverificationdecision.AiConsumerVerificationDecisionResult;

/**
 * Approval input copied from a verification-decision result plus a
 * synthetic context. Unlike the 072 result, this record may hold
 * {@code verificationApproved=true} so the boundary can detect that
 * flag instead of treating it as a clinical grant.
 */
public record AiConsumerEnforcementVerificationApprovalInput(
        boolean decisionResultPresent,
        boolean verificationDecisionAvailable,
        boolean verificationDecisionEvaluated,
        boolean verificationApproved,
        boolean executionVerified,
        boolean clinicalDataAccessGranted,
        boolean clinicalDataAccessAllowed,
        boolean clinicalDataAccessEnforced,
        boolean requiresHumanReview,
        ClinicalDataEnforcementVerificationApprovalContext approval) {

    public static AiConsumerEnforcementVerificationApprovalInput from(
            AiConsumerVerificationDecisionResult decision) {
        if (decision == null) {
            return null;
        }
        return of(decision, ClinicalDataEnforcementVerificationApprovalContext.laboratory());
    }

    public static AiConsumerEnforcementVerificationApprovalInput of(
            AiConsumerVerificationDecisionResult decision,
            ClinicalDataEnforcementVerificationApprovalContext approval) {
        if (decision == null) {
            return null;
        }
        return new AiConsumerEnforcementVerificationApprovalInput(
                true,
                decision.verificationDecisionAvailable(),
                decision.verificationDecisionEvaluated(),
                decision.verificationApproved(),
                decision.executionVerified(),
                decision.clinicalDataAccessGranted(),
                decision.clinicalDataAccessAllowed(),
                decision.clinicalDataAccessEnforced(),
                decision.requiresHumanReview(),
                approval);
    }

    public AiConsumerEnforcementVerificationApprovalInput withVerificationApproved(boolean value) {
        return new AiConsumerEnforcementVerificationApprovalInput(
                decisionResultPresent,
                verificationDecisionAvailable,
                verificationDecisionEvaluated,
                value,
                executionVerified,
                clinicalDataAccessGranted,
                clinicalDataAccessAllowed,
                clinicalDataAccessEnforced,
                requiresHumanReview,
                approval);
    }

    public AiConsumerEnforcementVerificationApprovalInput withClinicalDataAccessGranted(boolean value) {
        return new AiConsumerEnforcementVerificationApprovalInput(
                decisionResultPresent,
                verificationDecisionAvailable,
                verificationDecisionEvaluated,
                verificationApproved,
                executionVerified,
                value,
                clinicalDataAccessAllowed,
                clinicalDataAccessEnforced,
                requiresHumanReview,
                approval);
    }

    public AiConsumerEnforcementVerificationApprovalInput withExecutionVerified(boolean value) {
        return new AiConsumerEnforcementVerificationApprovalInput(
                decisionResultPresent,
                verificationDecisionAvailable,
                verificationDecisionEvaluated,
                verificationApproved,
                value,
                clinicalDataAccessGranted,
                clinicalDataAccessAllowed,
                clinicalDataAccessEnforced,
                requiresHumanReview,
                approval);
    }
}
