package lab.healthcare.fhir.projection;

/**
 * Allowlisted Condition projection. Never includes Condition.code, narrative, or subject.
 */
public record RetainedCondition(String resourceType, String clinicalStatus) {

    public RetainedCondition {
        resourceType = resourceType == null ? "" : resourceType.trim();
        clinicalStatus = clinicalStatus == null ? "" : clinicalStatus.trim();
    }
}
