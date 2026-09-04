package lab.healthcare.fhir.routing;

/**
 * Safe diagnosis of an authenticated DiagnosticReport search. Not a clinical payload.
 */
public enum FhirDiagnosticReportSearchOutcome {
    DIAGNOSTIC_REPORT_SEARCH_SUCCEEDED,
    PATIENT_CONTEXT_NOT_CONFIGURED,
    AUTHENTICATION_REQUIRED,
    AUTHENTICATION_REJECTED,
    AUTHORIZATION_DENIED,
    CAPABILITY_UNSUPPORTED,
    DEPENDENCY_FAILURE
}
