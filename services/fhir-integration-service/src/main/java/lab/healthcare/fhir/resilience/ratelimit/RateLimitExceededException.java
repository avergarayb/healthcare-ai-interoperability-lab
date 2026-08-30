package lab.healthcare.fhir.resilience.ratelimit;

import lab.healthcare.fhir.exception.FhirErrorCategory;
import lab.healthcare.fhir.exception.FhirErrorDetails;

/**
 * Local admission rejection: the destination quota for this window is exhausted.
 * Distinct from FHIR, routing, circuit, and bulkhead failures.
 */
public class RateLimitExceededException extends RuntimeException {

    private final FhirErrorDetails details;

    public RateLimitExceededException(String destination) {
        this(new FhirErrorDetails(
                FhirErrorCategory.RATE_LIMITED,
                null,
                "READ",
                destination,
                "Patient",
                null,
                FhirErrorCategory.RATE_LIMITED.safeMessage()));
    }

    private RateLimitExceededException(FhirErrorDetails details) {
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
