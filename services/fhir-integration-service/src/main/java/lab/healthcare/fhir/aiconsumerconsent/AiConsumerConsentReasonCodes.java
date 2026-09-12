package lab.healthcare.fhir.aiconsumerconsent;

/**
 * Stable consent-boundary reason codes. Never include clinical values
 * or vendor names.
 */
public final class AiConsumerConsentReasonCodes {

    public static final String MISSING_CONSUMER_AUTHORIZATION_RESULT = "MISSING_CONSUMER_AUTHORIZATION_RESULT";
    public static final String CONSUMER_AUTHORIZATION_NOT_AVAILABLE = "CONSUMER_AUTHORIZATION_NOT_AVAILABLE";
    public static final String UNEXPECTED_CONSUMER_AUTHORIZATION = "UNEXPECTED_CONSUMER_AUTHORIZATION";
    public static final String MISSING_CONSENT_CONTEXT = "MISSING_CONSENT_CONTEXT";
    public static final String CONSENT_REFERENCE_NOT_VERIFIED = "CONSENT_REFERENCE_NOT_VERIFIED";
    public static final String UNTRUSTED_CONSENT_ASSERTION = "UNTRUSTED_CONSENT_ASSERTION";
    public static final String MISSING_PURPOSE = "MISSING_PURPOSE";
    public static final String PURPOSE_NOT_APPROVED = "PURPOSE_NOT_APPROVED";
    public static final String UNKNOWN_OR_MISSING_PURPOSE = "UNKNOWN_OR_MISSING_PURPOSE";
    public static final String UNTRUSTED_PURPOSE_ASSERTION = "UNTRUSTED_PURPOSE_ASSERTION";
    public static final String MISSING_DATA_SCOPE = "MISSING_DATA_SCOPE";
    public static final String UNTRUSTED_DATA_SCOPE_ASSERTION = "UNTRUSTED_DATA_SCOPE_ASSERTION";
    public static final String MISSING_TENANT_CONTEXT = "MISSING_TENANT_CONTEXT";
    public static final String HUMAN_REVIEW_NOT_COMPLETED = "HUMAN_REVIEW_NOT_COMPLETED";

    private AiConsumerConsentReasonCodes() {
    }
}
