package lab.healthcare.fhir.clinicalread;

/**
 * Stable failure for the clinical read API. The message is the error code and
 * contains no clinical payload.
 */
public final class ClinicalReadException extends RuntimeException {

    private final int httpStatus;

    private ClinicalReadException(String code, int httpStatus) {
        super(code);
        this.httpStatus = httpStatus;
    }

    public String code() {
        return getMessage();
    }

    public int httpStatus() {
        return httpStatus;
    }

    public static ClinicalReadException notFound() {
        return new ClinicalReadException("not_found", 404);
    }

    public static ClinicalReadException unavailable() {
        return new ClinicalReadException("unavailable", 503);
    }

    public static ClinicalReadException destinationNotSupported() {
        return new ClinicalReadException("destination_not_supported", 409);
    }

    public static ClinicalReadException invalidRequest() {
        return new ClinicalReadException("invalid_request", 400);
    }
}
