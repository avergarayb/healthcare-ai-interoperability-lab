package lab.healthcare.fhir.connectivity;

/**
 * Transport-level probe result. Distinct from FHIR resource operations.
 */
public enum FhirConnectivityOutcome {
    REACHABLE,
    UNREACHABLE,
    SKIPPED
}
