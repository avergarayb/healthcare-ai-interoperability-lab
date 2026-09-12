package lab.healthcare.fhir.aigateway;

import lab.healthcare.fhir.agent.AgentDecision;
import lab.healthcare.fhir.firstai.FirstAiComponentStatus;
import lab.healthcare.fhir.firstai.FirstAiProcessingStatus;
import lab.healthcare.fhir.pipeline.PipelineStageStatus;

import java.util.List;

/**
 * Execution-gate verdict. Never includes record values, tokens, Patient
 * identifiers, or FHIR JSON.
 */
public record AiExecutionDecision(
        AiExecutionStatus executionDecision,
        FirstAiProcessingStatus processingStatus,
        PipelineStageStatus pipelineStatus,
        boolean clinicalDataAvailable,
        AgentDecision agentDecision,
        FirstAiComponentStatus componentStatus,
        boolean requiresHumanReview,
        boolean modelCalled,
        boolean modelCallAuthorized,
        String reasonCode,
        String executionReason,
        List<String> warnings,
        String medicationRequestsStatus,
        boolean contractValid,
        boolean usable,
        String destination,
        String correlationId) {

    public AiExecutionDecision {
        if (executionDecision == null) {
            throw new IllegalArgumentException("AI execution decision must be provided");
        }
        if (processingStatus == null) {
            throw new IllegalArgumentException("AI execution processing status must be provided");
        }
        if (pipelineStatus == null) {
            throw new IllegalArgumentException("AI execution pipeline status must be provided");
        }
        if (agentDecision == null) {
            throw new IllegalArgumentException("AI execution agent decision must be provided");
        }
        if (componentStatus == null) {
            throw new IllegalArgumentException("AI execution component status must be provided");
        }
        if (processingStatus != FirstAiProcessingStatus.NOT_EXECUTED) {
            throw new IllegalArgumentException("AI execution gate must not execute model processing");
        }
        if (modelCalled) {
            throw new IllegalArgumentException("AI execution gate must not call a model");
        }
        if (modelCallAuthorized) {
            throw new IllegalArgumentException("Eligibility does not authorize a model call");
        }
        if (!requiresHumanReview) {
            throw new IllegalArgumentException("AI execution gate requires human review");
        }
        reasonCode = blankToEmpty(reasonCode);
        executionReason = blankToEmpty(executionReason);
        medicationRequestsStatus = blankToEmpty(medicationRequestsStatus);
        destination = blankToEmpty(destination);
        correlationId = blankToEmpty(correlationId);
        warnings = copied(warnings);
    }

    @Override
    public String toString() {
        return "AiExecutionDecision[executionDecision="
                + executionDecision
                + ", processingStatus="
                + processingStatus
                + ", agentDecision="
                + agentDecision
                + ", pipelineStatus="
                + pipelineStatus
                + ", clinicalDataAvailable="
                + clinicalDataAvailable
                + ", requiresHumanReview="
                + requiresHumanReview
                + ", modelCalled="
                + modelCalled
                + ", modelCallAuthorized="
                + modelCallAuthorized
                + ", reasonCode="
                + reasonCode
                + ", executionReason="
                + executionReason
                + ", warnings="
                + warnings.size()
                + ", medicationRequestsStatus="
                + medicationRequestsStatus
                + "]";
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
