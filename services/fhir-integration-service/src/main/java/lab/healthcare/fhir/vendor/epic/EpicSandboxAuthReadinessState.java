package lab.healthcare.fhir.vendor.epic;

/**
 * Authentication-readiness of the Epic sandbox profile. Not a Patient read
 * and not certification.
 */
public enum EpicSandboxAuthReadinessState {
    NOT_CONFIGURED,
    DISABLED,
    CONFIGURED,
    READY_FOR_AUTHORIZATION,
    INVALID_CONFIGURATION
}
