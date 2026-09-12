package lab.healthcare.fhir.aiconsumer;

import lab.healthcare.fhir.agent.AgentDecision;
import lab.healthcare.fhir.aigateway.AiExecutionStatus;
import lab.healthcare.fhir.firstai.FirstAiComponentStatus;
import lab.healthcare.fhir.firstai.FirstAiProcessingStatus;
import lab.healthcare.fhir.pipeline.PipelineStageStatus;

import java.util.List;

/**
 * Internal AI Consumer Contract v1. Never includes record values, tokens,
 * Patient identifiers, or FHIR JSON. Ready is not dispatched and not
 * authorized.
 */
public record AiConsumerContract(
        String contractVersion,
        AiConsumerContractStatus contractStatus,
        AiConsumerDispatchStatus dispatchStatus,
        PipelineStageStatus pipelineStatus,
        boolean clinicalDataAvailable,
        AgentDecision agentDecision,
        FirstAiComponentStatus componentStatus,
        AiExecutionStatus executionDecision,
        boolean requiresHumanReview,
        boolean modelCalled,
        boolean modelCallAuthorized,
        FirstAiProcessingStatus processingStatus,
        List<String> reasonCodes,
        List<String> warnings,
        String medicationRequestsStatus,
        boolean contractValid,
        boolean usable,
        String destination,
        String correlationId) {

    public AiConsumerContract {
        if (contractVersion == null || !AiConsumerContractVersion.V1.equals(contractVersion.trim())) {
            throw new IllegalArgumentException("AI consumer contract version must be v1");
        }
        if (contractStatus == null) {
            throw new IllegalArgumentException("AI consumer contract status must be provided");
        }
        if (dispatchStatus == null) {
            throw new IllegalArgumentException("AI consumer dispatch status must be provided");
        }
        if (pipelineStatus == null) {
            throw new IllegalArgumentException("AI consumer pipeline status must be provided");
        }
        if (agentDecision == null) {
            throw new IllegalArgumentException("AI consumer agent decision must be provided");
        }
        if (componentStatus == null) {
            throw new IllegalArgumentException("AI consumer component status must be provided");
        }
        if (executionDecision == null) {
            throw new IllegalArgumentException("AI consumer execution decision must be provided");
        }
        if (processingStatus == null) {
            throw new IllegalArgumentException("AI consumer processing status must be provided");
        }
        if (dispatchStatus != AiConsumerDispatchStatus.NOT_DISPATCHED) {
            throw new IllegalArgumentException("AI consumer contract must not be dispatched");
        }
        if (processingStatus != FirstAiProcessingStatus.NOT_EXECUTED) {
            throw new IllegalArgumentException("AI consumer contract must not execute model processing");
        }
        if (modelCalled) {
            throw new IllegalArgumentException("AI consumer contract must not call a model");
        }
        if (modelCallAuthorized) {
            throw new IllegalArgumentException(AiConsumerReasonCodes.PREMATURE_MODEL_AUTHORIZATION);
        }
        if (!requiresHumanReview) {
            throw new IllegalArgumentException("AI consumer contract requires human review");
        }
        if (contractStatus != AiConsumerContractStatus.from(executionDecision)) {
            throw new IllegalArgumentException("AI consumer contract status must copy the execution decision");
        }
        contractVersion = AiConsumerContractVersion.V1;
        medicationRequestsStatus = blankToEmpty(medicationRequestsStatus);
        destination = blankToEmpty(destination);
        correlationId = blankToEmpty(correlationId);
        reasonCodes = copied(reasonCodes);
        warnings = copied(warnings);
    }

    @Override
    public String toString() {
        return "AiConsumerContract[contractVersion="
                + contractVersion
                + ", contractStatus="
                + contractStatus
                + ", dispatchStatus="
                + dispatchStatus
                + ", executionDecision="
                + executionDecision
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
                + ", processingStatus="
                + processingStatus
                + ", reasonCodes="
                + reasonCodes.size()
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
