package lab.healthcare.fhir.connectivity;

import lab.healthcare.fhir.exception.FhirErrorCategory;

/**
 * Result of a transport-level endpoint check. Reachable does not mean Patient
 * access, SMART login, or vendor certification.
 */
public record FhirConnectivityStatus(
        FhirConnectivityOutcome outcome,
        Integer httpStatus,
        FhirErrorCategory error,
        String endpointKind) {

    public FhirConnectivityStatus {
        if (outcome == null) {
            throw new IllegalArgumentException("Connectivity outcome must be provided");
        }
        endpointKind = endpointKind == null || endpointKind.isBlank() ? "metadata" : endpointKind.trim();
        if (outcome == FhirConnectivityOutcome.REACHABLE && error != null) {
            throw new IllegalArgumentException("Reachable status must not include an error category");
        }
        if (outcome == FhirConnectivityOutcome.UNREACHABLE && error == null) {
            throw new IllegalArgumentException("Unreachable status must include an error category");
        }
    }

    public static FhirConnectivityStatus reachable(int httpStatus) {
        return new FhirConnectivityStatus(FhirConnectivityOutcome.REACHABLE, httpStatus, null, "metadata");
    }

    public static FhirConnectivityStatus unreachable(FhirErrorCategory error, Integer httpStatus) {
        return new FhirConnectivityStatus(FhirConnectivityOutcome.UNREACHABLE, httpStatus, error, "metadata");
    }

    public static FhirConnectivityStatus skipped() {
        return new FhirConnectivityStatus(FhirConnectivityOutcome.SKIPPED, null, null, "metadata");
    }

    public boolean reachable() {
        return outcome == FhirConnectivityOutcome.REACHABLE;
    }

    @Override
    public String toString() {
        return "FhirConnectivityStatus[outcome="
                + outcome
                + ", httpStatus="
                + httpStatus
                + ", error="
                + error
                + ", endpointKind="
                + endpointKind
                + "]";
    }
}
