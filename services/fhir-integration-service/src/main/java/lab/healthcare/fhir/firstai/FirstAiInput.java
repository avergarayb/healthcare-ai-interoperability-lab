package lab.healthcare.fhir.firstai;

import lab.healthcare.fhir.aiboundary.AiBoundaryResult;

/**
 * Authorized input to the first AI component. Contains only an
 * {@link AiBoundaryResult}.
 */
public record FirstAiInput(AiBoundaryResult boundary) {

    public FirstAiInput {
        if (boundary == null) {
            throw new IllegalArgumentException("First AI component requires an AI boundary result");
        }
    }

    public static FirstAiInput of(AiBoundaryResult boundary) {
        return new FirstAiInput(boundary);
    }
}
