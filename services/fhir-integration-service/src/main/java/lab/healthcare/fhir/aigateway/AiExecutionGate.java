package lab.healthcare.fhir.aigateway;

import lab.healthcare.fhir.agent.AgentDecision;
import lab.healthcare.fhir.firstai.FirstAiComponentStatus;
import lab.healthcare.fhir.firstai.FirstAiProcessingStatus;
import lab.healthcare.fhir.firstai.FirstAiResult;
import lab.healthcare.fhir.pipeline.PipelineStageStatus;

/**
 * Local execution gate. Decides eligibility only. Never authorizes or calls a
 * model.
 */
public final class AiExecutionGate {

    private AiExecutionGate() {
    }

    public static AiExecutionDecision evaluate(FirstAiResult firstAi) {
        return evaluate(AiExecutionMapper.from(firstAi));
    }

    public static AiExecutionDecision evaluate(AiExecutionInput input) {
        if (input == null) {
            throw new IllegalArgumentException("AI execution gate input must be provided");
        }
        AiExecutionStatus status = decide(input);
        return new AiExecutionDecision(
                status,
                FirstAiProcessingStatus.NOT_EXECUTED,
                input.pipelineStatus(),
                input.clinicalDataAvailable(),
                input.agentDecision(),
                input.componentStatus(),
                true,
                false,
                false,
                input.reasonCode(),
                executionReason(status),
                input.warnings(),
                input.medicationRequestsStatus(),
                input.contractValid(),
                input.usable(),
                input.destination(),
                input.correlationId());
    }

    private static AiExecutionStatus decide(AiExecutionInput input) {
        if (input.agentDecision() == AgentDecision.BLOCKED) {
            return AiExecutionStatus.BLOCKED;
        }
        if (input.agentDecision() == AgentDecision.REQUIRES_HUMAN_REVIEW) {
            return AiExecutionStatus.REQUIRES_HUMAN_REVIEW;
        }
        if (!input.clinicalDataAvailable()) {
            return AiExecutionStatus.NOT_ELIGIBLE;
        }
        if (input.pipelineStatus() == PipelineStageStatus.PARTIAL) {
            return AiExecutionStatus.REQUIRES_HUMAN_REVIEW;
        }
        if (input.agentDecision() == AgentDecision.READY
                && input.componentStatus() == FirstAiComponentStatus.PREPARED
                && input.processingStatus() == FirstAiProcessingStatus.NOT_EXECUTED
                && input.clinicalDataAvailable()) {
            return AiExecutionStatus.ELIGIBLE_BUT_NOT_AUTHORIZED;
        }
        return AiExecutionStatus.NOT_ELIGIBLE;
    }

    private static String executionReason(AiExecutionStatus status) {
        return switch (status) {
            case ELIGIBLE_BUT_NOT_AUTHORIZED -> AiExecutionReasonCodes.ELIGIBLE_BUT_NOT_AUTHORIZED;
            case NOT_ELIGIBLE -> AiExecutionReasonCodes.NOT_ELIGIBLE;
            case BLOCKED, REQUIRES_HUMAN_REVIEW -> status.name();
        };
    }
}
