package lab.healthcare.fhir.exception;

public class FhirClientException extends RuntimeException {

    private final FhirErrorDetails details;

    public FhirClientException(FhirErrorDetails details, Throwable cause) {
        super(requireDetails(details).message(), cause);
        this.details = details;
    }

    public FhirErrorDetails details() {
        return details;
    }

    public FhirErrorCategory category() {
        return details.category();
    }

    public static FhirClientException from(Throwable cause) {
        if (cause instanceof FhirClientException existing) {
            return existing;
        }
        return new FhirClientException(FhirErrorClassifier.classify(cause), cause);
    }

    private static FhirErrorDetails requireDetails(FhirErrorDetails details) {
        if (details == null) {
            throw new IllegalArgumentException("Error details must be provided");
        }
        return details;
    }
}
