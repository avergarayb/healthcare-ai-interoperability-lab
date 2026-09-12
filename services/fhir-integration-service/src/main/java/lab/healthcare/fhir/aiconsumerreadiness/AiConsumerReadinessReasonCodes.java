package lab.healthcare.fhir.aiconsumerreadiness;

/**
 * Stable readiness reason codes. Never include clinical values or vendor names.
 */
public final class AiConsumerReadinessReasonCodes {

    public static final String READY_FOR_FUTURE_HANDOFF = "READY_FOR_FUTURE_HANDOFF";
    public static final String POLICY_REJECTED = "POLICY_REJECTED";
    public static final String POLICY_REQUIRES_HUMAN_REVIEW = "POLICY_REQUIRES_HUMAN_REVIEW";
    public static final String POLICY_RESULT_MISSING = "POLICY_RESULT_MISSING";
    public static final String INCONSISTENT_EXECUTION_STATE = "INCONSISTENT_EXECUTION_STATE";
    public static final String HUMAN_REVIEW_FLAG_MISSING = "HUMAN_REVIEW_FLAG_MISSING";
    public static final String CONTRACT_VERSION_NOT_SUPPORTED = "CONTRACT_VERSION_NOT_SUPPORTED";
    public static final String OPERATION_NOT_SUPPORTED_FOR_READINESS = "OPERATION_NOT_SUPPORTED_FOR_READINESS";
    public static final String SCOPE_NOT_SUPPORTED_FOR_READINESS = "SCOPE_NOT_SUPPORTED_FOR_READINESS";

    private AiConsumerReadinessReasonCodes() {
    }
}
