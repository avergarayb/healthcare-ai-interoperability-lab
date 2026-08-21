package lab.healthcare.fhir.client;

public class FhirClientException extends RuntimeException {

    public FhirClientException(String message, Throwable cause) {
        super(message, cause);
    }
}
