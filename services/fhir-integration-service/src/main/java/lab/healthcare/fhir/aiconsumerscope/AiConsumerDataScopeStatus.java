package lab.healthcare.fhir.aiconsumerscope;

/**
 * Clinical data-scope and minimization verdict. Task 067 never approves
 * a scope and never grants clinical access.
 */
public enum AiConsumerDataScopeStatus {
    DATA_SCOPE_NOT_DECLARED,
    DATA_SCOPE_DECLARED_NOT_EVALUATED,
    MINIMIZATION_NOT_EVALUATED,
    PURPOSE_SCOPE_ALIGNMENT_NOT_VERIFIED,
    SCOPE_REQUIRES_HUMAN_REVIEW,
    SCOPE_BLOCKED,
    NOT_READY_FOR_CLINICAL_DATA_ACCESS
}
