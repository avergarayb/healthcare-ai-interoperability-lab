package lab.healthcare.fhir.routing;

/**
 * Safe diagnosis of a controlled Patient read. Not a clinical payload.
 */
public enum FhirPatientReadOutcome {
    PATIENT_READ_SUCCEEDED,
    PATIENT_CONTEXT_NOT_CONFIGURED,
    AUTHENTICATION_REQUIRED,
    AUTHENTICATION_REJECTED,
    AUTHORIZATION_DENIED,
    CAPABILITY_UNSUPPORTED,
    PATIENT_NOT_FOUND,
    DEPENDENCY_FAILURE
}
