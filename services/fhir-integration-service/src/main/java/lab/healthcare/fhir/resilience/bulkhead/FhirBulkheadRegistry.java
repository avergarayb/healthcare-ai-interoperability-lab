package lab.healthcare.fhir.resilience.bulkhead;

import org.springframework.stereotype.Component;

import java.util.concurrent.ConcurrentHashMap;

/**
 * One bulkhead per destination/profile name.
 */
@Component
public class FhirBulkheadRegistry {

    private final FhirBulkheadPolicy policy;
    private final ConcurrentHashMap<String, FhirBulkhead> bulkheads = new ConcurrentHashMap<>();

    public FhirBulkheadRegistry() {
        this(FhirBulkheadPolicy.defaults());
    }

    public static FhirBulkheadRegistry of(FhirBulkheadPolicy policy) {
        return new FhirBulkheadRegistry(policy);
    }

    FhirBulkheadRegistry(FhirBulkheadPolicy policy) {
        if (policy == null) {
            throw new IllegalArgumentException("Bulkhead policy must be provided");
        }
        this.policy = policy;
    }

    public FhirBulkheadPolicy policy() {
        return policy;
    }

    public FhirBulkhead forDestination(String destination) {
        if (destination == null || destination.isBlank()) {
            throw new IllegalArgumentException("Bulkhead destination must be provided");
        }
        return bulkheads.computeIfAbsent(destination, name -> new FhirBulkhead(name, policy));
    }
}
