package lab.healthcare.fhir.resilience;

import lab.healthcare.fhir.exception.FhirErrorCategory;
import lab.healthcare.fhir.exception.FhirErrorDetails;

/**
 * Fail-fast signal: the destination was not contacted because the circuit is OPEN
 * (or a HALF_OPEN probe is already in flight). Distinct from FHIR and routing failures.
 */
public class CircuitBreakerOpenException extends RuntimeException {

    private final FhirErrorDetails details;

    public CircuitBreakerOpenException(String destination) {
        this(new FhirErrorDetails(
                FhirErrorCategory.CIRCUIT_OPEN,
                null,
                "READ",
                destination,
                "Patient",
                null,
                FhirErrorCategory.CIRCUIT_OPEN.safeMessage()));
    }

    private CircuitBreakerOpenException(FhirErrorDetails details) {
        super(details.message());
        this.details = details;
    }

    public FhirErrorDetails details() {
        return details;
    }

    public FhirErrorCategory category() {
        return details.category();
    }
}
