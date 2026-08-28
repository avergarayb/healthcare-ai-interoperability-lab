package lab.healthcare.fhir.routing;

import org.hl7.fhir.r4.model.Patient;
import org.hl7.fhir.r4.model.Resource;

public record RoutingRequest(String destination, Resource resource, String correlationId) {

    public RoutingRequest {
        if (destination == null || destination.isBlank()) {
            throw new IllegalArgumentException("Routing destination must be provided");
        }
        if (resource == null) {
            throw new IllegalArgumentException("Routing resource must be provided");
        }
        destination = destination.trim();
        correlationId = correlationId == null || correlationId.isBlank() ? null : correlationId.trim();
    }

    public RoutingRequest(String destination, Resource resource) {
        this(destination, resource, null);
    }

    public static RoutingRequest readPatient(String destination, String logicalId) {
        return readPatient(destination, logicalId, null);
    }

    public static RoutingRequest readPatient(String destination, String logicalId, String correlationId) {
        if (logicalId == null || logicalId.isBlank()) {
            throw new IllegalArgumentException("Patient logical ID must be provided");
        }
        Patient patient = new Patient();
        patient.setId(logicalId.trim());
        return new RoutingRequest(destination, patient, correlationId);
    }
}
