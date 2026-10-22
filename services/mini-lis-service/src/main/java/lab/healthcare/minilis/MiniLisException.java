package lab.healthcare.minilis;

/**
 * Domain failure. The code is stable and carries no clinical payload.
 */
public final class MiniLisException extends RuntimeException {

    private final int httpStatus;

    private MiniLisException(String code, int httpStatus) {
        super(code);
        this.httpStatus = httpStatus;
    }

    public String code() {
        return getMessage();
    }

    public int httpStatus() {
        return httpStatus;
    }

    public static MiniLisException invalidRequest() {
        return new MiniLisException("invalid_request", 400);
    }

    public static MiniLisException unauthorized() {
        return new MiniLisException("unauthorized", 401);
    }

    public static MiniLisException notFound() {
        return new MiniLisException("not_found", 404);
    }

    public static MiniLisException duplicate() {
        return new MiniLisException("duplicate", 409);
    }

    public static MiniLisException invalidTransition() {
        return new MiniLisException("invalid_transition", 409);
    }

    public static MiniLisException unavailable() {
        return new MiniLisException("unavailable", 503);
    }
}
