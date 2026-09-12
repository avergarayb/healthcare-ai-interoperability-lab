package lab.healthcare.fhir.aiconsumerenforcement;

/**
 * Stable enforcement reason codes. Never include clinical values or
 * vendor names.
 */
public final class AiConsumerClinicalDataEnforcementReasonCodes {

    public static final String MISSING_ACCESS_RESULT = "MISSING_ACCESS_RESULT";
    public static final String ACCESS_NOT_GRANTED = "ACCESS_NOT_GRANTED";
    public static final String ENFORCEMENT_REQUIRES_ACCESS_DECISION = "ENFORCEMENT_REQUIRES_ACCESS_DECISION";
    public static final String ENFORCEMENT_REQUIRES_REAL_AUTHORIZATION =
            "ENFORCEMENT_REQUIRES_REAL_AUTHORIZATION";
    public static final String MISSING_TENANT_SCOPE = "MISSING_TENANT_SCOPE";
    public static final String UNTRUSTED_ENFORCEMENT_ASSERTION = "UNTRUSTED_ENFORCEMENT_ASSERTION";
    public static final String NOT_ENFORCED_FOR_CLINICAL_DATA_ACCESS = "NOT_ENFORCED_FOR_CLINICAL_DATA_ACCESS";

    private AiConsumerClinicalDataEnforcementReasonCodes() {
    }
}
