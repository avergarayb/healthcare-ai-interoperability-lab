package lab.healthcare.fhir.exception;

public enum FhirErrorCategory {
    VALIDATION_ERROR("FHIR request is invalid"),
    AUTHENTICATION_ERROR("FHIR authentication failed"),
    AUTHORIZATION_ERROR("FHIR authorization failed"),
    NOT_FOUND("FHIR resource not found"),
    CONFLICT("FHIR resource conflict"),
    SERVER_ERROR("FHIR server unavailable"),
    TIMEOUT("FHIR request timed out"),
    CONNECTION_ERROR("FHIR connection failed"),
    UNKNOWN("FHIR integration failed"),
    CIRCUIT_OPEN("FHIR destination circuit is open"),
    RATE_LIMITED("FHIR destination rate limit exceeded"),
    BULKHEAD_FULL("FHIR destination bulkhead is full");

    private final String safeMessage;

    FhirErrorCategory(String safeMessage) {
        this.safeMessage = safeMessage;
    }

    public String safeMessage() {
        return safeMessage;
    }
}
