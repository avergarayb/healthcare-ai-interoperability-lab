package lab.healthcare.fhir.exception;

public class FhirClientException extends RuntimeException {

    public FhirClientException(String message, Throwable cause) {
        super(message, cause);
    }
}
