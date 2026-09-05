package lab.healthcare.fhir.modelboundary;

/**
 * MedicationRequest record that may cross the v1 model boundary. Never includes
 * medication or dosage.
 */
public record BoundaryMedicationRequest(String resourceType, String status, String intent) {

    public BoundaryMedicationRequest {
        resourceType = resourceType == null ? "" : resourceType.trim();
        status = status == null ? "" : status.trim();
        intent = intent == null ? "" : intent.trim();
    }
}
