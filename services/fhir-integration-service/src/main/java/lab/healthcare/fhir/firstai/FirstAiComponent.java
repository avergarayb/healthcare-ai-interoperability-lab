package lab.healthcare.fhir.firstai;

import lab.healthcare.fhir.aiboundary.AiBoundaryResult;

/**
 * First isolated AI component. Consumes only {@link AiBoundaryResult}. Never
 * calls a model, EHR, or FHIR.
 */
public final class FirstAiComponent {

    private FirstAiComponent() {
    }

    public static FirstAiResult process(FirstAiInput input) {
        if (input == null) {
            throw new IllegalArgumentException("First AI component input must be provided");
        }
        return FirstAiMapper.from(input.boundary());
    }

    public static FirstAiResult process(AiBoundaryResult boundary) {
        return process(FirstAiInput.of(boundary));
    }
}
