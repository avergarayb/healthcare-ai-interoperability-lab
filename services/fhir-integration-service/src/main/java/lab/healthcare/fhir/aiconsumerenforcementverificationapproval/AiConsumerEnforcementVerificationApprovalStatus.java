package lab.healthcare.fhir.aiconsumerenforcementverificationapproval;

/**
 * Synthetic verification-approval verdict. Task 073 never approves
 * clinical access and never reads FHIR.
 */
public enum AiConsumerEnforcementVerificationApprovalStatus {
    VERIFICATION_APPROVAL_NOT_AVAILABLE,
    BLOCKED,
    HUMAN_REVIEW_REQUIRED,
    NOT_ELIGIBLE_FOR_APPROVAL
}
