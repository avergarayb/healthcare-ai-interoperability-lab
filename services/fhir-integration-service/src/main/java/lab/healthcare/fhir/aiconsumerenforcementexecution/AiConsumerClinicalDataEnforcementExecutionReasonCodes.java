package lab.healthcare.fhir.aiconsumerenforcementexecution;

/**
 * Stable enforcement-execution reason codes. Never include clinical
 * values or vendor names.
 */
public final class AiConsumerClinicalDataEnforcementExecutionReasonCodes {

    public static final String MISSING_ENFORCEMENT_RESULT = "MISSING_ENFORCEMENT_RESULT";
    public static final String ENFORCEMENT_NOT_EXECUTED = "ENFORCEMENT_NOT_EXECUTED";
    public static final String EXECUTION_REQUIRES_ENFORCEMENT_DECISION =
            "EXECUTION_REQUIRES_ENFORCEMENT_DECISION";
    public static final String EXECUTION_REQUIRES_REAL_AUTHORIZATION =
            "EXECUTION_REQUIRES_REAL_AUTHORIZATION";
    public static final String EXECUTION_REQUIRES_HUMAN_REVIEW = "EXECUTION_REQUIRES_HUMAN_REVIEW";
    public static final String MISSING_TENANT_SCOPE = "MISSING_TENANT_SCOPE";
    public static final String UNTRUSTED_EXECUTION_ASSERTION = "UNTRUSTED_EXECUTION_ASSERTION";

    private AiConsumerClinicalDataEnforcementExecutionReasonCodes() {
    }
}
