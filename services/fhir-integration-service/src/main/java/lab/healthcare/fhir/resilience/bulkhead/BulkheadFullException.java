package lab.healthcare.fhir.resilience.bulkhead;

import lab.healthcare.fhir.exception.FhirErrorCategory;
import lab.healthcare.fhir.exception.FhirErrorDetails;

/**
 * Local capacity rejection: all concurrent permits for this destination are in use.
 * Distinct from FHIR, routing, circuit, and rate-limit failures.
 */
public class BulkheadFullException extends RuntimeException {

    private final FhirErrorDetails details;

    public BulkheadFullException(String destination) {
        this(new FhirErrorDetails(
                FhirErrorCategory.BULKHEAD_FULL,
                null,
                "READ",
                destination,
                "Patient",
                null,
                FhirErrorCategory.BULKHEAD_FULL.safeMessage()));
    }

    private BulkheadFullException(FhirErrorDetails details) {
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
