package lab.healthcare.fhir.aiconsumerenforcementverificationdecision;

/**
 * Stable verification-decision reason codes. Never include clinical
 * values or vendor names.
 */
public final class AiConsumerVerificationDecisionReasonCodes {

    public static final String MISSING_VERIFICATION_RESULT = "MISSING_VERIFICATION_RESULT";
    public static final String VERIFICATION_DECISION_NOT_AVAILABLE = "VERIFICATION_DECISION_NOT_AVAILABLE";
    public static final String DECISION_REQUIRES_VERIFICATION_RESULT =
            "DECISION_REQUIRES_VERIFICATION_RESULT";
    public static final String DECISION_REQUIRES_VERIFIED_EVIDENCE = "DECISION_REQUIRES_VERIFIED_EVIDENCE";
    public static final String DECISION_REQUIRES_REAL_POLICY_PROVIDER =
            "DECISION_REQUIRES_REAL_POLICY_PROVIDER";
    public static final String DECISION_REQUIRES_REAL_AUTHORIZATION =
            "DECISION_REQUIRES_REAL_AUTHORIZATION";
    public static final String DECISION_REQUIRES_HUMAN_REVIEW = "DECISION_REQUIRES_HUMAN_REVIEW";
    public static final String MISSING_TENANT_SCOPE = "MISSING_TENANT_SCOPE";
    public static final String UNTRUSTED_DECISION_ASSERTION = "UNTRUSTED_DECISION_ASSERTION";

    private AiConsumerVerificationDecisionReasonCodes() {
    }
}
