package lab.healthcare.fhir.modelboundary;

/**
 * Condition record that may cross the v1 model boundary. Never includes
 * Condition.code, narrative, or subject.
 */
public record BoundaryCondition(String resourceType, String clinicalStatusCode) {

    public BoundaryCondition {
        resourceType = resourceType == null ? "" : resourceType.trim();
        clinicalStatusCode = clinicalStatusCode == null ? "" : clinicalStatusCode.trim();
    }
}
