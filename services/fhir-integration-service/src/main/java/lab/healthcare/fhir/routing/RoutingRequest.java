package lab.healthcare.fhir.routing;

import org.hl7.fhir.r4.model.Patient;
import org.hl7.fhir.r4.model.Resource;

public record RoutingRequest(String destination, Resource resource) {

    public RoutingRequest {
        if (destination == null || destination.isBlank()) {
            throw new IllegalArgumentException("Routing destination must be provided");
        }
        if (resource == null) {
            throw new IllegalArgumentException("Routing resource must be provided");
        }
        destination = destination.trim();
    }

    public static RoutingRequest readPatient(String destination, String logicalId) {
        if (logicalId == null || logicalId.isBlank()) {
            throw new IllegalArgumentException("Patient logical ID must be provided");
        }
        Patient patient = new Patient();
        patient.setId(logicalId.trim());
        return new RoutingRequest(destination, patient);
    }
}
