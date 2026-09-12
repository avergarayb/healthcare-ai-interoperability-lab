package lab.healthcare.fhir.aiconsumer;

import lab.healthcare.fhir.aigateway.AiExecutionDecision;

/**
 * Builds AI Consumer Contract v1. Never dispatches, never calls a model.
 */
public final class AiConsumerContractService {

    private AiConsumerContractService() {
    }

    public static AiConsumerContract prepare(AiExecutionDecision decision) {
        if (decision == null) {
            throw new IllegalArgumentException("AI consumer contract requires an execution decision");
        }
        if (decision.modelCallAuthorized()) {
            throw new IllegalArgumentException(AiConsumerReasonCodes.PREMATURE_MODEL_AUTHORIZATION);
        }
        return AiConsumerContractMapper.from(decision);
    }
}
