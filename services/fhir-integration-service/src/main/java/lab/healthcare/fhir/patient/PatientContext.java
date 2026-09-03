package lab.healthcare.fhir.patient;

/**
 * Explicit Patient subject for a controlled integration workflow. Not a FHIR
 * Patient resource and not an OAuth identity ({@code fhirUser}).
 */
public record PatientContext(String destination, String patientId, PatientContextSource source) {

    public PatientContext {
        if (destination == null || destination.isBlank()) {
            throw new IllegalArgumentException("Destination must be provided");
        }
        if (patientId == null || patientId.isBlank()) {
            throw new IllegalArgumentException("Patient identifier must be provided");
        }
        if (source == null) {
            throw new IllegalArgumentException("Patient context source must be provided");
        }
        destination = destination.trim();
        patientId = patientId.trim();
    }

    @Override
    public String toString() {
        return "PatientContext[destination=" + destination + ", source=" + source + ", hasPatientId=true]";
    }
}
