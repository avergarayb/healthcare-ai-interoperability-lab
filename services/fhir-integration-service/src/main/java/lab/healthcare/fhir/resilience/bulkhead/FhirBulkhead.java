package lab.healthcare.fhir.resilience.bulkhead;

import java.util.concurrent.Semaphore;
import java.util.function.Supplier;

/**
 * Per-destination concurrency limiter. {@link #execute} always releases the
 * permit in {@code finally}.
 */
public class FhirBulkhead {

    private final String destination;
    private final FhirBulkheadPolicy policy;
    private final Semaphore semaphore;

    public FhirBulkhead(String destination, FhirBulkheadPolicy policy) {
        if (destination == null || destination.isBlank()) {
            throw new IllegalArgumentException("Bulkhead destination must be provided");
        }
        if (policy == null) {
            throw new IllegalArgumentException("Bulkhead policy must be provided");
        }
        this.destination = destination;
        this.policy = policy;
        this.semaphore = new Semaphore(policy.maxConcurrentOperations());
    }

    public String destination() {
        return destination;
    }

    public FhirBulkheadPolicy policy() {
        return policy;
    }

    public int availablePermits() {
        return semaphore.availablePermits();
    }

    public void acquire() {
        if (!semaphore.tryAcquire()) {
            throw new BulkheadFullException(destination);
        }
    }

    public void release() {
        semaphore.release();
    }

    public <T> T execute(Supplier<T> operation) {
        if (operation == null) {
            throw new IllegalArgumentException("Bulkhead operation must be provided");
        }
        acquire();
        try {
            return operation.get();
        } finally {
            release();
        }
    }
}
