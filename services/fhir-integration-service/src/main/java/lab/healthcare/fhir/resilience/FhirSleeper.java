package lab.healthcare.fhir.resilience;

/**
 * Wait abstraction so retry tests do not call {@code Thread.sleep}.
 */
@FunctionalInterface
public interface FhirSleeper {

    void sleep(long delayMs);

    static FhirSleeper threadSleep() {
        return delayMs -> {
            if (delayMs <= 0L) {
                return;
            }
            try {
                Thread.sleep(delayMs);
            } catch (InterruptedException ex) {
                Thread.currentThread().interrupt();
                throw new IllegalStateException("Retry wait interrupted", ex);
            }
        };
    }

    static FhirSleeper noop() {
        return delayMs -> {
        };
    }
}
