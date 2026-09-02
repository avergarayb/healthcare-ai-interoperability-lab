package lab.healthcare.fhir.routing;

/**
 * Safe diagnosis of an authenticated FHIR read/search. Not a clinical payload.
 */
public enum FhirAuthenticatedReadOutcome {
    AUTHENTICATED_READ_SUCCEEDED,
    AUTHENTICATION_REQUIRED,
    AUTHENTICATION_REJECTED,
    AUTHORIZATION_DENIED,
    CAPABILITY_UNSUPPORTED,
    DEPENDENCY_FAILURE
}
