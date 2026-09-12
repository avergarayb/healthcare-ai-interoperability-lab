package lab.healthcare.fhir.aigateway;

/**
 * Technical execution-gate verdict. Eligibility is not model authorization.
 */
public enum AiExecutionStatus {
    NOT_ELIGIBLE,
    BLOCKED,
    REQUIRES_HUMAN_REVIEW,
    ELIGIBLE_BUT_NOT_AUTHORIZED
}
