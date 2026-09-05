package lab.healthcare.fhir.projection;

/**
 * Allowlisted Patient projection. Never includes id, name, birthDate, or identifiers.
 */
public record RetainedPatient(String resourceType) {

    public RetainedPatient {
        resourceType = resourceType == null ? "" : resourceType.trim();
    }
}
