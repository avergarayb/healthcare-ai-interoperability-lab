package lab.healthcare.fhir.aiconsumeraccess;

/**
 * Clinical data-access request verdict. Task 068 never grants access
 * and never enables a FHIR read.
 */
public enum AiConsumerClinicalDataAccessStatus {
    ACCESS_REQUEST_NOT_DECLARED,
    ACCESS_REQUEST_DECLARED_NOT_EVALUATED,
    ACCESS_REQUEST_REQUIRES_SCOPE,
    ACCESS_REQUEST_REQUIRES_REAL_AUTHORIZATION,
    ACCESS_REQUEST_BLOCKED,
    ACCESS_REQUEST_REQUIRES_HUMAN_REVIEW,
    NOT_GRANTED_FOR_CLINICAL_DATA_ACCESS
}
