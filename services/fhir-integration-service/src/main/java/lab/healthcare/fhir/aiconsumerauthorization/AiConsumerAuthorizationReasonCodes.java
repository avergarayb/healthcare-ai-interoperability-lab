package lab.healthcare.fhir.aiconsumerauthorization;

/**
 * Stable consumer-authorization reason codes. Never include clinical values
 * or vendor names.
 */
public final class AiConsumerAuthorizationReasonCodes {

    public static final String MISSING_HANDOFF_AUTHORIZATION_RESULT = "MISSING_HANDOFF_AUTHORIZATION_RESULT";
    public static final String HANDOFF_NOT_AUTHORIZED = "HANDOFF_NOT_AUTHORIZED";
    public static final String UNEXPECTED_HANDOFF_AUTHORIZATION = "UNEXPECTED_HANDOFF_AUTHORIZATION";
    public static final String REAL_AUTHENTICATION_AUTHORIZATION_NOT_IMPLEMENTED =
            "REAL_AUTHENTICATION_AUTHORIZATION_NOT_IMPLEMENTED";
    public static final String CONSUMER_IDENTITY_NOT_VERIFIED = "CONSUMER_IDENTITY_NOT_VERIFIED";
    public static final String UNTRUSTED_AUTHENTICATION_ASSERTION = "UNTRUSTED_AUTHENTICATION_ASSERTION";
    public static final String UNTRUSTED_AUTHORIZATION_ASSERTION = "UNTRUSTED_AUTHORIZATION_ASSERTION";
    public static final String SCOPE_NOT_VERIFIED = "SCOPE_NOT_VERIFIED";
    public static final String MISSING_TENANT_CONTEXT = "MISSING_TENANT_CONTEXT";
    public static final String HUMAN_REVIEW_FLAG_MISSING = "HUMAN_REVIEW_FLAG_MISSING";

    private AiConsumerAuthorizationReasonCodes() {
    }
}
