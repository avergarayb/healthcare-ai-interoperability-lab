package lab.healthcare.fhir.resilience;

import lab.healthcare.fhir.exception.FhirClientException;
import lab.healthcare.fhir.exception.FhirErrorCategory;
import lab.healthcare.fhir.exception.FhirErrorClassifier;

import org.springframework.stereotype.Component;

import java.util.concurrent.TimeUnit;
import java.util.function.Supplier;

/**
 * Runs an idempotent integration operation with bounded exponential backoff.
 * Does not know Patient JSON, destinations, or credentials.
 */
@Component
public class FhirRetryExecutor {

    private final FhirRetryPolicy policy;
    private final FhirSleeper sleeper;

    public FhirRetryExecutor() {
        this(FhirRetryPolicy.defaults(), FhirSleeper.threadSleep());
    }

    public static FhirRetryExecutor immediate() {
        return of(FhirRetryPolicy.defaults(), FhirSleeper.noop());
    }

    public static FhirRetryExecutor of(FhirRetryPolicy policy, FhirSleeper sleeper) {
        return new FhirRetryExecutor(policy, sleeper);
    }

    FhirRetryExecutor(FhirRetryPolicy policy, FhirSleeper sleeper) {
        if (policy == null) {
            throw new IllegalArgumentException("Retry policy must be provided");
        }
        if (sleeper == null) {
            throw new IllegalArgumentException("Retry sleeper must be provided");
        }
        this.policy = policy;
        this.sleeper = sleeper;
    }

    public FhirRetryPolicy policy() {
        return policy;
    }

    public <T> T execute(Supplier<T> operation) {
        return execute(operation, attempt -> {
        });
    }

    public <T> T execute(Supplier<T> operation, FhirRetryObserver observer) {
        if (operation == null) {
            throw new IllegalArgumentException("Retry operation must be provided");
        }
        if (observer == null) {
            throw new IllegalArgumentException("Retry observer must be provided");
        }
        RuntimeException lastFailure = null;
        for (int attempt = 1; attempt <= policy.maxAttempts(); attempt++) {
            long started = System.nanoTime();
            try {
                T result = operation.get();
                observer.onAttempt(new FhirRetryAttempt(
                        attempt, policy.maxAttempts(), true, false, 0L, elapsedMs(started), null));
                return result;
            } catch (RuntimeException ex) {
                lastFailure = ex;
                FhirRetryDecision decision = policy.decide(categoryOf(ex), attempt);
                observer.onAttempt(new FhirRetryAttempt(
                        attempt,
                        policy.maxAttempts(),
                        false,
                        decision.retry(),
                        decision.delayMs(),
                        elapsedMs(started),
                        ex));
                if (!decision.retry()) {
                    throw ex;
                }
                sleeper.sleep(decision.delayMs());
            }
        }
        throw lastFailure;
    }

    private static FhirErrorCategory categoryOf(RuntimeException ex) {
        if (ex instanceof FhirClientException fhir) {
            return fhir.category();
        }
        return FhirErrorClassifier.classify(ex).category();
    }

    private static long elapsedMs(long startedNanos) {
        return TimeUnit.NANOSECONDS.toMillis(Math.max(0L, System.nanoTime() - startedNanos));
    }
}
