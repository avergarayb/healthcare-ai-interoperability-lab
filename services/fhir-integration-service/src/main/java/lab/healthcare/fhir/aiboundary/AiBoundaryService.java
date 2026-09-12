package lab.healthcare.fhir.aiboundary;

import java.util.UUID;

/**
 * Coordinates the AI boundary payload. Never calls a model, EHR, or FHIR.
 */
public final class AiBoundaryService {

    private AiBoundaryService() {
    }

    public static AiBoundaryResult prepare(AiBoundaryInput input) {
        return prepare(input, UUID.randomUUID().toString());
    }

    public static AiBoundaryResult prepare(AiBoundaryInput input, String correlationId) {
        if (input == null) {
            throw new IllegalArgumentException("AI boundary input must be provided");
        }
        return AiBoundaryMapper.from(input, correlationId);
    }
}
