package lab.healthcare.fhir.aiconsumerenforcementverification;

/**
 * Clinical data-access enforcement-execution verification verdict.
 * Task 071 never verifies execution and never enables a FHIR read.
 */
public enum AiConsumerClinicalDataEnforcementExecutionVerificationStatus {
    VERIFICATION_INPUT_NOT_AVAILABLE,
    VERIFICATION_BLOCKED,
    VERIFICATION_REQUIRES_EXECUTION_RESULT,
    VERIFICATION_REQUIRES_EVIDENCE,
    VERIFICATION_REQUIRES_REAL_PROVIDER,
    VERIFICATION_REQUIRES_HUMAN_REVIEW,
    VERIFICATION_NOT_AVAILABLE,
    NOT_VERIFIED_FOR_CLINICAL_DATA_ACCESS
}
