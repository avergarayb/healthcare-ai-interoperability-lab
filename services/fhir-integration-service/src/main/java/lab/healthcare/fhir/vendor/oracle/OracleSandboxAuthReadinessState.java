package lab.healthcare.fhir.vendor.oracle;

/**
 * Authentication-readiness of the Oracle Health sandbox profile. Not a Patient
 * read and not certification.
 */
public enum OracleSandboxAuthReadinessState {
    NOT_CONFIGURED,
    DISABLED,
    CONFIGURED,
    READY_FOR_AUTHORIZATION,
    INVALID_CONFIGURATION
}
