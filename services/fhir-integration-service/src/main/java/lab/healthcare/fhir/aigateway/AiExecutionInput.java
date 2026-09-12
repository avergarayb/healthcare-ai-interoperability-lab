package lab.healthcare.fhir.aigateway;

import lab.healthcare.fhir.agent.AgentDecision;
import lab.healthcare.fhir.firstai.FirstAiComponentStatus;
import lab.healthcare.fhir.firstai.FirstAiProcessingStatus;
import lab.healthcare.fhir.pipeline.PipelineStageStatus;

import java.util.List;

/**
 * Minimum frontier fields the execution gate may inspect. Premature
 * {@code modelCallAuthorized=true} is rejected, not normalized.
 */
public record AiExecutionInput(
        AgentDecision agentDecision,
        PipelineStageStatus pipelineStatus,
        boolean clinicalDataAvailable,
        FirstAiComponentStatus componentStatus,
        FirstAiProcessingStatus processingStatus,
        boolean requiresHumanReview,
        boolean modelCalled,
        boolean modelCallAuthorized,
        String reasonCode,
        List<String> warnings,
        String medicationRequestsStatus,
        boolean contractValid,
        boolean usable,
        String destination,
        String correlationId) {

    public AiExecutionInput {
        if (agentDecision == null) {
            throw new IllegalArgumentException("AI execution gate requires an agent decision");
        }
        if (pipelineStatus == null) {
            throw new IllegalArgumentException("AI execution gate requires a pipeline status");
        }
        if (componentStatus == null) {
            throw new IllegalArgumentException("AI execution gate requires a first AI component status");
        }
        if (processingStatus == null) {
            throw new IllegalArgumentException("AI execution gate requires a processing status");
        }
        if (processingStatus != FirstAiProcessingStatus.NOT_EXECUTED) {
            throw new IllegalArgumentException("AI execution gate must not receive executed processing");
        }
        if (modelCalled) {
            throw new IllegalArgumentException("AI execution gate must not receive a model call");
        }
        if (modelCallAuthorized) {
            throw new IllegalArgumentException(AiExecutionReasonCodes.PREMATURE_MODEL_AUTHORIZATION);
        }
        if (!requiresHumanReview) {
            throw new IllegalArgumentException("AI execution gate requires human review");
        }
        reasonCode = blankToEmpty(reasonCode);
        medicationRequestsStatus = blankToEmpty(medicationRequestsStatus);
        destination = blankToEmpty(destination);
        correlationId = blankToEmpty(correlationId);
        warnings = copied(warnings);
    }

    private static String blankToEmpty(String value) {
        return value == null ? "" : value.trim();
    }

    private static List<String> copied(List<String> values) {
        if (values == null || values.isEmpty()) {
            return List.of();
        }
        return values.stream()
                .filter(value -> value != null && !value.isBlank())
                .map(String::trim)
                .toList();
    }
}
