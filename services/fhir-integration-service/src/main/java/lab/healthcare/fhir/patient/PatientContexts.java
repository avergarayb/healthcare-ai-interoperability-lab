package lab.healthcare.fhir.patient;

import java.util.Optional;

/**
 * Builds a {@link PatientContext} only when destination and Patient ID are
 * present. Does not search, guess, or call a FHIR server.
 */
public final class PatientContexts {

    private PatientContexts() {
    }

    public static Optional<PatientContext> configured(String destination, String patientId) {
        if (destination == null || destination.isBlank()) {
            return Optional.empty();
        }
        if (patientId == null || patientId.isBlank()) {
            return Optional.empty();
        }
        return Optional.of(new PatientContext(destination.trim(), patientId.trim(), PatientContextSource.CONFIGURED));
    }
}
