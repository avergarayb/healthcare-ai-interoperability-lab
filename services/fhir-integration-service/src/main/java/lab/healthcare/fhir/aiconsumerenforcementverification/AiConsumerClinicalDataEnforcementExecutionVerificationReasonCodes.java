package lab.healthcare.fhir.aiconsumerenforcementverification;

/**
 * Stable verification reason codes. Never include clinical values or
 * vendor names.
 */
public final class AiConsumerClinicalDataEnforcementExecutionVerificationReasonCodes {

    public static final String MISSING_EXECUTION_RESULT = "MISSING_EXECUTION_RESULT";
    public static final String EXECUTION_NOT_VERIFIED = "EXECUTION_NOT_VERIFIED";
    public static final String VERIFICATION_REQUIRES_EXECUTION_RESULT =
            "VERIFICATION_REQUIRES_EXECUTION_RESULT";
    public static final String VERIFICATION_REQUIRES_EVIDENCE = "VERIFICATION_REQUIRES_EVIDENCE";
    public static final String VERIFICATION_REQUIRES_REAL_PROVIDER = "VERIFICATION_REQUIRES_REAL_PROVIDER";
    public static final String VERIFICATION_REQUIRES_HUMAN_REVIEW = "VERIFICATION_REQUIRES_HUMAN_REVIEW";
    public static final String MISSING_TENANT_SCOPE = "MISSING_TENANT_SCOPE";
    public static final String UNTRUSTED_VERIFICATION_ASSERTION = "UNTRUSTED_VERIFICATION_ASSERTION";

    private AiConsumerClinicalDataEnforcementExecutionVerificationReasonCodes() {
    }
}
