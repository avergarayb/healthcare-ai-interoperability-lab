package lab.healthcare.fhir.aiconsumerenforcementverificationdecision;

/**
 * Clinical data-access enforcement verification-decision verdict.
 * Task 072 never approves verification and never enables a FHIR read.
 */
public enum AiConsumerVerificationDecisionStatus {
    DECISION_INPUT_NOT_AVAILABLE,
    DECISION_BLOCKED,
    DECISION_REQUIRES_VERIFICATION_RESULT,
    DECISION_REQUIRES_VERIFIED_EVIDENCE,
    DECISION_REQUIRES_REAL_POLICY_PROVIDER,
    DECISION_REQUIRES_REAL_AUTHORIZATION,
    DECISION_REQUIRES_HUMAN_REVIEW,
    VERIFICATION_DECISION_NOT_AVAILABLE
}
