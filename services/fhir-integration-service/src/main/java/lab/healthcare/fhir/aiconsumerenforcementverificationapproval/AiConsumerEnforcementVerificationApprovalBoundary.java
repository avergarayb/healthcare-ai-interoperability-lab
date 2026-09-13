package lab.healthcare.fhir.aiconsumerenforcementverificationapproval;

import lab.healthcare.fhir.aiconsumerenforcementverificationdecision.AiConsumerVerificationDecisionResult;

/**
 * Deny-by-default enforcement verification-approval boundary. A
 * verification decision is not an approval and an approval is not a
 * clinical grant. Task 073 never reads FHIR.
 */
public final class AiConsumerEnforcementVerificationApprovalBoundary {

    private AiConsumerEnforcementVerificationApprovalBoundary() {
    }

    public static AiConsumerEnforcementVerificationApprovalResult evaluate(
            AiConsumerVerificationDecisionResult decision) {
        if (decision == null) {
            return missingDecision();
        }
        return evaluate(AiConsumerEnforcementVerificationApprovalInput.from(decision));
    }

    public static AiConsumerEnforcementVerificationApprovalResult evaluate(
            AiConsumerVerificationDecisionResult decision,
            ClinicalDataEnforcementVerificationApprovalContext approval) {
        if (decision == null) {
            return missingDecision();
        }
        if (approval == null) {
            return missingContext();
        }
        return evaluate(AiConsumerEnforcementVerificationApprovalInput.of(decision, approval));
    }

    public static AiConsumerEnforcementVerificationApprovalResult evaluate(
            AiConsumerEnforcementVerificationApprovalInput input) {
        if (input == null || !input.decisionResultPresent()) {
            return missingDecision();
        }
        ClinicalDataEnforcementVerificationApprovalContext approval = input.approval();
        if (approval == null) {
            return missingContext();
        }
        if (untrustedAssertion(input, approval)) {
            return result(
                    AiConsumerEnforcementVerificationApprovalStatus.HUMAN_REVIEW_REQUIRED,
                    AiConsumerEnforcementVerificationApprovalReasonCodes.SYNTHETIC_APPROVAL_CLAIMS_UNTRUSTED,
                    input,
                    approval);
        }
        if (approval.decisionAvailabilityCheckAttempted()) {
            return result(
                    AiConsumerEnforcementVerificationApprovalStatus.BLOCKED,
                    AiConsumerEnforcementVerificationApprovalReasonCodes.VERIFICATION_DECISION_NOT_AVAILABLE,
                    input,
                    approval);
        }
        if (approval.decisionEvaluatedCheckAttempted()) {
            return result(
                    AiConsumerEnforcementVerificationApprovalStatus.BLOCKED,
                    AiConsumerEnforcementVerificationApprovalReasonCodes.VERIFICATION_DECISION_NOT_EVALUATED,
                    input,
                    approval);
        }
        if (approval.approvalHumanReviewRequired()) {
            return result(
                    AiConsumerEnforcementVerificationApprovalStatus.HUMAN_REVIEW_REQUIRED,
                    AiConsumerEnforcementVerificationApprovalReasonCodes
                            .HUMAN_REVIEW_REQUIRED_BY_PREVIOUS_BOUNDARY,
                    input,
                    approval);
        }
        if (approval.evidenceCheckAttempted()) {
            return result(
                    AiConsumerEnforcementVerificationApprovalStatus.BLOCKED,
                    AiConsumerEnforcementVerificationApprovalReasonCodes
                            .VERIFICATION_APPROVAL_EVIDENCE_NOT_AVAILABLE,
                    input,
                    approval);
        }
        return result(
                AiConsumerEnforcementVerificationApprovalStatus.VERIFICATION_APPROVAL_NOT_AVAILABLE,
                AiConsumerEnforcementVerificationApprovalReasonCodes.VERIFICATION_APPROVAL_NOT_AVAILABLE,
                input,
                approval);
    }

    private static boolean untrustedAssertion(
            AiConsumerEnforcementVerificationApprovalInput input,
            ClinicalDataEnforcementVerificationApprovalContext approval) {
        return input.verificationApproved()
                || input.executionVerified()
                || input.clinicalDataAccessGranted()
                || input.clinicalDataAccessAllowed()
                || input.clinicalDataAccessEnforced()
                || approval.hasUntrustedApprovalClaim();
    }

    private static AiConsumerEnforcementVerificationApprovalResult missingDecision() {
        return result(
                AiConsumerEnforcementVerificationApprovalStatus.BLOCKED,
                AiConsumerEnforcementVerificationApprovalReasonCodes.VERIFICATION_DECISION_RESULT_MISSING,
                null,
                ClinicalDataEnforcementVerificationApprovalContext.laboratory());
    }

    private static AiConsumerEnforcementVerificationApprovalResult missingContext() {
        return result(
                AiConsumerEnforcementVerificationApprovalStatus.BLOCKED,
                AiConsumerEnforcementVerificationApprovalReasonCodes.VERIFICATION_APPROVAL_CONTEXT_MISSING,
                null,
                ClinicalDataEnforcementVerificationApprovalContext.laboratory());
    }

    private static AiConsumerEnforcementVerificationApprovalResult result(
            AiConsumerEnforcementVerificationApprovalStatus status,
            String reason,
            AiConsumerEnforcementVerificationApprovalInput input,
            ClinicalDataEnforcementVerificationApprovalContext approval) {
        boolean synthetic = approval.hasUntrustedApprovalClaim()
                || approval.approvalHumanReviewRequired()
                || approval.decisionAvailabilityCheckAttempted()
                || approval.decisionEvaluatedCheckAttempted()
                || approval.evidenceCheckAttempted();
        return AiConsumerEnforcementVerificationApprovalResult.denied(
                status,
                reason,
                input != null && input.decisionResultPresent(),
                synthetic
                        ? ClinicalDataEnforcementVerificationApprovalContext.SOURCE_SYNTHETIC_APPROVAL
                        : ClinicalDataEnforcementVerificationApprovalContext.SOURCE_LABORATORY);
    }
}
