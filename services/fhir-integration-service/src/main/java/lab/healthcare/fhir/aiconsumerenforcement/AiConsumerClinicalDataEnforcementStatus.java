package lab.healthcare.fhir.aiconsumerenforcement;

/**
 * Clinical data-access enforcement verdict. Task 069 never enforces
 * access and never enables a FHIR read.
 */
public enum AiConsumerClinicalDataEnforcementStatus {
    ENFORCEMENT_INPUT_NOT_AVAILABLE,
    ENFORCEMENT_BLOCKED,
    ENFORCEMENT_REQUIRES_ACCESS_DECISION,
    ENFORCEMENT_REQUIRES_REAL_AUTHORIZATION,
    ENFORCEMENT_REQUIRES_HUMAN_REVIEW,
    ENFORCEMENT_NOT_AVAILABLE,
    NOT_ENFORCED_FOR_CLINICAL_DATA_ACCESS
}
