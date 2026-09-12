package lab.healthcare.fhir.aiconsumeraccess;

/**
 * Stable clinical-access reason codes. Never include clinical values or
 * vendor names.
 */
public final class AiConsumerClinicalDataAccessReasonCodes {

    public static final String MISSING_DATA_SCOPE_RESULT = "MISSING_DATA_SCOPE_RESULT";
    public static final String SCOPE_NOT_PREPARED = "SCOPE_NOT_PREPARED";
    public static final String ACCESS_REQUEST_NOT_DECLARED = "ACCESS_REQUEST_NOT_DECLARED";
    public static final String ACCESS_REQUEST_DECLARED_NOT_EVALUATED = "ACCESS_REQUEST_DECLARED_NOT_EVALUATED";
    public static final String ACCESS_REQUEST_REQUIRES_SCOPE = "ACCESS_REQUEST_REQUIRES_SCOPE";
    public static final String ACCESS_REQUEST_REQUIRES_REAL_AUTHORIZATION =
            "ACCESS_REQUEST_REQUIRES_REAL_AUTHORIZATION";
    public static final String MISSING_TENANT_SCOPE = "MISSING_TENANT_SCOPE";
    public static final String UNTRUSTED_ACCESS_ASSERTION = "UNTRUSTED_ACCESS_ASSERTION";
    public static final String NOT_GRANTED_FOR_CLINICAL_DATA_ACCESS = "NOT_GRANTED_FOR_CLINICAL_DATA_ACCESS";

    private AiConsumerClinicalDataAccessReasonCodes() {
    }
}
