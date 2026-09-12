package lab.healthcare.fhir.aihandoffauthorization;

/**
 * Stable authorization reason codes. Never include clinical values or vendor names.
 */
public final class AiHandoffAuthorizationReasonCodes {

    public static final String REAL_AUTHORIZATION_NOT_IMPLEMENTED = "REAL_AUTHORIZATION_NOT_IMPLEMENTED";
    public static final String READINESS_RESULT_MISSING = "READINESS_RESULT_MISSING";
    public static final String READINESS_BLOCKED = "READINESS_BLOCKED";
    public static final String READINESS_REQUIRES_HUMAN_REVIEW = "READINESS_REQUIRES_HUMAN_REVIEW";
    public static final String READINESS_NOT_COMPLETE = "READINESS_NOT_COMPLETE";
    public static final String INCONSISTENT_EXECUTION_STATE = "INCONSISTENT_EXECUTION_STATE";
    public static final String HUMAN_REVIEW_FLAG_MISSING = "HUMAN_REVIEW_FLAG_MISSING";
    public static final String HANDOFF_SCOPE_NOT_GRANTED = "HANDOFF_SCOPE_NOT_GRANTED";

    private AiHandoffAuthorizationReasonCodes() {
    }
}
