package lab.healthcare.fhir.federation;

/**
 * Stable federation failure. The message is an error code and contains no
 * clinical payload.
 */
public final class FederationException extends RuntimeException {

    private final int httpStatus;

    private FederationException(String code, int httpStatus) {
        super(code);
        this.httpStatus = httpStatus;
    }

    public String code() {
        return getMessage();
    }

    public int httpStatus() {
        return httpStatus;
    }

    public static FederationException invalidRequest() {
        return new FederationException("invalid_request", 400);
    }

    public static FederationException forbidden(String code) {
        return new FederationException(code, 403);
    }
}
