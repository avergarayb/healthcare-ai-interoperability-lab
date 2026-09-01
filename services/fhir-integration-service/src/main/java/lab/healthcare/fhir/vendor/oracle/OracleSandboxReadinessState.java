package lab.healthcare.fhir.vendor.oracle;

/**
 * Connection-readiness of the Oracle Health sandbox profile. Not certification
 * and not proof of Patient access.
 */
public enum OracleSandboxReadinessState {
    NOT_CONFIGURED,
    DISABLED,
    CONFIGURED,
    READY_FOR_CONNECTIVITY_CHECK,
    INVALID_CONFIGURATION
}
