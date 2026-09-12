package lab.healthcare.fhir.aiconsumerenforcementexecution;

/**
 * Clinical data-access enforcement-execution verdict. Task 070 never
 * executes enforcement and never enables a FHIR read.
 */
public enum AiConsumerClinicalDataEnforcementExecutionStatus {
    EXECUTION_INPUT_NOT_AVAILABLE,
    EXECUTION_BLOCKED,
    EXECUTION_REQUIRES_ENFORCEMENT_DECISION,
    EXECUTION_REQUIRES_REAL_AUTHORIZATION,
    EXECUTION_REQUIRES_HUMAN_REVIEW,
    EXECUTION_NOT_AVAILABLE,
    NOT_EXECUTED_FOR_CLINICAL_DATA_ACCESS
}
