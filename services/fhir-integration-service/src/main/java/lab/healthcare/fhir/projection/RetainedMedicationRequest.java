package lab.healthcare.fhir.projection;

/**
 * Allowlisted MedicationRequest projection. Never includes medication or dosage.
 */
public record RetainedMedicationRequest(String resourceType, String status, String intent) {

    public RetainedMedicationRequest {
        resourceType = resourceType == null ? "" : resourceType.trim();
        status = status == null ? "" : status.trim();
        intent = intent == null ? "" : intent.trim();
    }
}
