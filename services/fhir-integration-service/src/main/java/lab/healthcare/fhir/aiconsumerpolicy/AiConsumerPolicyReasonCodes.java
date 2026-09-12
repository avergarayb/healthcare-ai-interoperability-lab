package lab.healthcare.fhir.aiconsumerpolicy;

/**
 * Stable policy reason codes. Never include clinical values or vendor names.
 */
public final class AiConsumerPolicyReasonCodes {

    public static final String ALLOWED_FOR_FUTURE_CONSUMPTION = "ALLOWED_FOR_FUTURE_CONSUMPTION";
    public static final String CONSUMER_NOT_AUTHENTICATED = "CONSUMER_NOT_AUTHENTICATED";
    public static final String CONSUMER_NOT_AUTHORIZED = "CONSUMER_NOT_AUTHORIZED";
    public static final String REQUIRED_SCOPE_MISSING = "REQUIRED_SCOPE_MISSING";
    public static final String CONTRACT_VERSION_NOT_SUPPORTED = "CONTRACT_VERSION_NOT_SUPPORTED";
    public static final String OPERATION_NOT_ALLOWED = "OPERATION_NOT_ALLOWED";
    public static final String TENANT_CONTEXT_REQUIRED = "TENANT_CONTEXT_REQUIRED";
    public static final String CONTRACT_NOT_CONSUMABLE = "CONTRACT_NOT_CONSUMABLE";
    public static final String CONTRACT_REQUIRES_HUMAN_REVIEW = "CONTRACT_REQUIRES_HUMAN_REVIEW";
    public static final String CONTRACT_NOT_ELIGIBLE = "CONTRACT_NOT_ELIGIBLE";
    public static final String PREMATURE_MODEL_AUTHORIZATION = "PREMATURE_MODEL_AUTHORIZATION";
    public static final String DISPATCH_NOT_SUPPORTED = "DISPATCH_NOT_SUPPORTED";
    public static final String INVALID_POLICY_INPUT = "INVALID_POLICY_INPUT";

    private AiConsumerPolicyReasonCodes() {
    }
}
