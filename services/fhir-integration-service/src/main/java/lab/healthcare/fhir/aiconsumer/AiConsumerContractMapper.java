package lab.healthcare.fhir.aiconsumer;

import lab.healthcare.fhir.aigateway.AiExecutionDecision;
import lab.healthcare.fhir.firstai.FirstAiProcessingStatus;

import java.util.ArrayList;
import java.util.List;

/**
 * Copies an {@link AiExecutionDecision} onto AI Consumer Contract v1. Does not
 * dispatch, fetch FHIR, or call a model.
 */
public final class AiConsumerContractMapper {

    private AiConsumerContractMapper() {
    }

    public static AiConsumerContract from(AiExecutionDecision decision) {
        if (decision == null) {
            throw new IllegalArgumentException("AI consumer contract requires an execution decision");
        }
        if (decision.modelCallAuthorized()) {
            throw new IllegalArgumentException(AiConsumerReasonCodes.PREMATURE_MODEL_AUTHORIZATION);
        }
        return new AiConsumerContract(
                AiConsumerContractVersion.V1,
                AiConsumerContractStatus.from(decision.executionDecision()),
                AiConsumerDispatchStatus.NOT_DISPATCHED,
                decision.pipelineStatus(),
                decision.clinicalDataAvailable(),
                decision.agentDecision(),
                decision.componentStatus(),
                decision.executionDecision(),
                true,
                false,
                false,
                FirstAiProcessingStatus.NOT_EXECUTED,
                reasonCodes(decision),
                decision.warnings(),
                decision.medicationRequestsStatus(),
                decision.contractValid(),
                decision.usable(),
                decision.destination(),
                decision.correlationId());
    }

    private static List<String> reasonCodes(AiExecutionDecision decision) {
        List<String> codes = new ArrayList<>();
        addIfPresent(codes, decision.reasonCode());
        addIfPresent(codes, decision.executionReason());
        return List.copyOf(codes);
    }

    private static void addIfPresent(List<String> codes, String value) {
        if (value == null || value.isBlank() || codes.contains(value)) {
            return;
        }
        codes.add(value.trim());
    }
}
