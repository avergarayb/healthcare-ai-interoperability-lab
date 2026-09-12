package lab.healthcare.fhir.firstai;

import lab.healthcare.fhir.aiboundary.AiBoundaryDecision;
import lab.healthcare.fhir.aiboundary.AiBoundaryResult;

/**
 * Copies an {@link AiBoundaryResult} onto the first AI component output. Does
 * not re-evaluate READY/BLOCKED rules, fetch FHIR, or call a model.
 */
public final class FirstAiMapper {

    private FirstAiMapper() {
    }

    public static FirstAiResult from(AiBoundaryResult boundary) {
        if (boundary == null) {
            throw new IllegalArgumentException("First AI component requires an AI boundary result");
        }
        AiBoundaryDecision decision = boundary.decision();
        return new FirstAiResult(
                FirstAiComponentStatus.from(decision.agentDecision()),
                FirstAiProcessingStatus.NOT_EXECUTED,
                decision.pipelineStatus(),
                decision.clinicalDataAvailable(),
                decision.agentDecision(),
                true,
                false,
                false,
                boundary.reasonCode(),
                boundary.warnings(),
                boundary.medicationRequestsStatus(),
                boundary.contractValid(),
                boundary.usable(),
                boundary.destination(),
                boundary.contractVersion(),
                boundary.correlationId());
    }
}
