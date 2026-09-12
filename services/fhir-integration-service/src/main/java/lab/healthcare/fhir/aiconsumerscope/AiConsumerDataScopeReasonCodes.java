package lab.healthcare.fhir.aiconsumerscope;

/**
 * Stable data-scope reason codes. Never include clinical values or
 * vendor names.
 */
public final class AiConsumerDataScopeReasonCodes {

    public static final String MISSING_CONSENT_RESULT = "MISSING_CONSENT_RESULT";
    public static final String CONSENT_NOT_AVAILABLE = "CONSENT_NOT_AVAILABLE";
    public static final String PURPOSE_NOT_VERIFIED = "PURPOSE_NOT_VERIFIED";
    public static final String DATA_SCOPE_NOT_DECLARED = "DATA_SCOPE_NOT_DECLARED";
    public static final String DATA_SCOPE_DECLARED_NOT_EVALUATED = "DATA_SCOPE_DECLARED_NOT_EVALUATED";
    public static final String MISSING_TENANT_SCOPE = "MISSING_TENANT_SCOPE";
    public static final String UNTRUSTED_SCOPE_ASSERTION = "UNTRUSTED_SCOPE_ASSERTION";
    public static final String NOT_READY_FOR_CLINICAL_DATA_ACCESS = "NOT_READY_FOR_CLINICAL_DATA_ACCESS";

    private AiConsumerDataScopeReasonCodes() {
    }
}
