package lab.healthcare.fhir.modelboundary;

/**
 * Observation record that may cross the v1 model boundary. Never includes
 * code, value, or interpretation.
 */
public record BoundaryObservation(String resourceType, String status) {

    public BoundaryObservation {
        resourceType = resourceType == null ? "" : resourceType.trim();
        status = status == null ? "" : status.trim();
    }
}
