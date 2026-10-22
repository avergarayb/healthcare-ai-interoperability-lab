package lab.healthcare.fhir.exchange;

/**
 * Stable exchange failure. The message is an error code and carries no clinical value.
 */
public final class ExchangeException extends RuntimeException {

    private final int status;
    private final String correlationId;

    private ExchangeException(String code, int status, String correlationId) {
        super(code);
        this.status = status;
        this.correlationId = correlationId;
    }

    public String code() {
        return getMessage();
    }

    public int status() {
        return status;
    }

    public String correlationId() {
        return correlationId;
    }

    public ExchangeException withCorrelation(String correlationId) {
        return new ExchangeException(code(), status, correlationId);
    }

    public static ExchangeException invalidRequest() {
        return new ExchangeException("invalid_request", 400, null);
    }

    public static ExchangeException forbidden() {
        return new ExchangeException("organization_forbidden", 403, null);
    }

    public static ExchangeException notFound() {
        return new ExchangeException("not_found", 404, null);
    }

    public static ExchangeException notRoutable() {
        return new ExchangeException("destination_not_routable", 409, null);
    }

    public static ExchangeException unavailable() {
        return new ExchangeException("destination_unavailable", 503, null);
    }

    public static ExchangeException rejected() {
        return new ExchangeException("destination_rejected", 409, null);
    }
}
