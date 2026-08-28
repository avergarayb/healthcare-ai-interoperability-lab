package lab.healthcare.fhir.routing;

import lab.healthcare.fhir.exception.FhirErrorCategory;
import lab.healthcare.fhir.exception.FhirErrorDetails;

public class RoutingException extends RuntimeException {

    private final FhirErrorDetails details;

    public RoutingException(FhirErrorDetails details) {
        this(details, null);
    }

    public RoutingException(FhirErrorDetails details, Throwable cause) {
        super(requireDetails(details).message(), cause);
        this.details = details;
    }

    public FhirErrorDetails details() {
        return details;
    }

    public FhirErrorCategory category() {
        return details.category();
    }

    static RoutingException fromRegistry(String destination, Throwable cause) {
        String message = cause.getMessage() == null ? "" : cause.getMessage();
        if (message.contains("Unknown FHIR server profile")) {
            return new RoutingException(
                    routingDetails(destination, "FHIR destination not found: " + destination), cause);
        }
        if (message.contains("disabled")) {
            return new RoutingException(
                    routingDetails(destination, "FHIR destination is disabled: " + destination), cause);
        }
        return new RoutingException(routingDetails(destination, "FHIR routing request is invalid"), cause);
    }

    private static FhirErrorDetails routingDetails(String destination, String message) {
        return new FhirErrorDetails(
                FhirErrorCategory.VALIDATION_ERROR, null, null, destination, null, null, message);
    }

    private static FhirErrorDetails requireDetails(FhirErrorDetails details) {
        if (details == null) {
            throw new IllegalArgumentException("Error details must be provided");
        }
        return details;
    }
}
