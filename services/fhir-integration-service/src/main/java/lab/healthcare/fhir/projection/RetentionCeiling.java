package lab.healthcare.fhir.projection;

/**
 * Application-controlled retention limit. Independent of the EHR {@code _count}
 * request and of any vendor destination.
 */
public final class RetentionCeiling {

    public static final int DEFAULT_LIMIT = 5;

    private final int limit;

    public RetentionCeiling() {
        this(DEFAULT_LIMIT);
    }

    public RetentionCeiling(int limit) {
        if (limit < 1) {
            throw new IllegalArgumentException("Retention ceiling must be at least 1");
        }
        this.limit = limit;
    }

    public int limit() {
        return limit;
    }

    public int retain(int receivedCount) {
        if (receivedCount < 0) {
            throw new IllegalArgumentException("Received count cannot be negative");
        }
        return Math.min(receivedCount, limit);
    }

    public boolean truncated(int receivedCount) {
        return receivedCount > limit;
    }
}
