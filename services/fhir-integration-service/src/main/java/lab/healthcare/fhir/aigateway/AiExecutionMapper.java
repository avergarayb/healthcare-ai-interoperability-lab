package lab.healthcare.fhir.aigateway;

import lab.healthcare.fhir.firstai.FirstAiResult;

/**
 * Copies a {@link FirstAiResult} onto execution-gate input. Does not
 * re-evaluate READY/BLOCKED rules, fetch FHIR, or call a model.
 */
public final class AiExecutionMapper {

    private AiExecutionMapper() {
    }

    public static AiExecutionInput from(FirstAiResult firstAi) {
        if (firstAi == null) {
            throw new IllegalArgumentException("AI execution gate requires a first AI result");
        }
        return new AiExecutionInput(
                firstAi.agentDecision(),
                firstAi.pipelineStatus(),
                firstAi.clinicalDataAvailable(),
                firstAi.componentStatus(),
                firstAi.processingStatus(),
                firstAi.requiresHumanReview(),
                firstAi.modelCalled(),
                firstAi.modelCallAuthorized(),
                firstAi.reasonCode(),
                firstAi.warnings(),
                firstAi.medicationRequestsStatus(),
                firstAi.contractValid(),
                firstAi.usable(),
                firstAi.destination(),
                firstAi.correlationId());
    }
}
