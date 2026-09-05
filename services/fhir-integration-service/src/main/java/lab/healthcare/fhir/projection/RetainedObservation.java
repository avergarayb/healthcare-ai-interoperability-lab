package lab.healthcare.fhir.projection;

/**
 * Allowlisted Observation projection. Never includes code, value, or interpretation.
 */
public record RetainedObservation(String resourceType, String status) {

    public RetainedObservation {
        resourceType = resourceType == null ? "" : resourceType.trim();
        status = status == null ? "" : status.trim();
    }
}
