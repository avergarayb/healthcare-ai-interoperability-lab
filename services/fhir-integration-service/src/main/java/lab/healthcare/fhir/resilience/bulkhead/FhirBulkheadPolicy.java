package lab.healthcare.fhir.resilience.bulkhead;

/**
 * Concurrent capacity for one destination. Rejects immediately when full.
 */
public record FhirBulkheadPolicy(int maxConcurrentOperations) {

    public static final int DEFAULT_MAX_CONCURRENT_OPERATIONS = 5;

    public FhirBulkheadPolicy {
        if (maxConcurrentOperations < 1) {
            throw new IllegalArgumentException("maxConcurrentOperations must be at least 1");
        }
    }

    public static FhirBulkheadPolicy defaults() {
        return new FhirBulkheadPolicy(DEFAULT_MAX_CONCURRENT_OPERATIONS);
    }
}
