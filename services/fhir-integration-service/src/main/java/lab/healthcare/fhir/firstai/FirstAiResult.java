package lab.healthcare.fhir.firstai;

import lab.healthcare.fhir.agent.AgentDecision;
import lab.healthcare.fhir.pipeline.PipelineStageStatus;

import java.util.List;

/**
 * Technical output of the first isolated AI component. Never includes record
 * values, tokens, Patient identifiers, or FHIR JSON.
 */
public record FirstAiResult(
        FirstAiComponentStatus componentStatus,
        FirstAiProcessingStatus processingStatus,
        PipelineStageStatus pipelineStatus,
        boolean clinicalDataAvailable,
        AgentDecision agentDecision,
        boolean requiresHumanReview,
        boolean modelCalled,
        boolean modelCallAuthorized,
        String reasonCode,
        List<String> warnings,
        String medicationRequestsStatus,
        boolean contractValid,
        boolean usable,
        String destination,
        String contractVersion,
        String correlationId) {

    public FirstAiResult {
        if (componentStatus == null) {
            throw new IllegalArgumentException("First AI component status must be provided");
        }
        if (processingStatus == null) {
            throw new IllegalArgumentException("First AI processing status must be provided");
        }
        if (pipelineStatus == null) {
            throw new IllegalArgumentException("First AI pipeline status must be provided");
        }
        if (agentDecision == null) {
            throw new IllegalArgumentException("First AI agent decision must be provided");
        }
        if (processingStatus != FirstAiProcessingStatus.NOT_EXECUTED) {
            throw new IllegalArgumentException("First AI component must not execute model processing");
        }
        if (modelCalled) {
            throw new IllegalArgumentException("First AI component must not call a model");
        }
        if (modelCallAuthorized) {
            throw new IllegalArgumentException("READY does not authorize a model call");
        }
        if (!requiresHumanReview) {
            throw new IllegalArgumentException("First AI component requires human review");
        }
        if (componentStatus != FirstAiComponentStatus.from(agentDecision)) {
            throw new IllegalArgumentException("First AI component status must copy the agent decision");
        }
        reasonCode = blankToEmpty(reasonCode);
        medicationRequestsStatus = blankToEmpty(medicationRequestsStatus);
        destination = blankToEmpty(destination);
        contractVersion = blankToEmpty(contractVersion);
        correlationId = blankToEmpty(correlationId);
        warnings = copied(warnings);
    }

    @Override
    public String toString() {
        return "FirstAiResult[componentStatus="
                + componentStatus
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
