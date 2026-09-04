package lab.healthcare.fhir.routing;

/**
 * Safe diagnosis of an authenticated Condition search. Not a clinical payload.
 */
public enum FhirConditionSearchOutcome {
    CONDITION_SEARCH_SUCCEEDED,
    PATIENT_CONTEXT_NOT_CONFIGURED,
    AUTHENTICATION_REQUIRED,
    AUTHENTICATION_REJECTED,
    AUTHORIZATION_DENIED,
    CAPABILITY_UNSUPPORTED,
    DEPENDENCY_FAILURE
}
