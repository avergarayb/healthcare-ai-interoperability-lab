package lab.healthcare.fhir.aiconsumer;

import lab.healthcare.fhir.aigateway.AiExecutionStatus;

/**
 * Preparation status of the AI consumer contract. {@link #READY} is not model
 * authorization and not dispatch.
 */
public enum AiConsumerContractStatus {
    READY,
    BLOCKED,
    REQUIRES_HUMAN_REVIEW,
    NOT_ELIGIBLE;

    public static AiConsumerContractStatus from(AiExecutionStatus executionDecision) {
        if (executionDecision == null) {
            throw new IllegalArgumentException("AI consumer contract requires an execution decision");
        }
        return switch (executionDecision) {
            case ELIGIBLE_BUT_NOT_AUTHORIZED -> READY;
            case BLOCKED -> BLOCKED;
            case REQUIRES_HUMAN_REVIEW -> REQUIRES_HUMAN_REVIEW;
            case NOT_ELIGIBLE -> NOT_ELIGIBLE;
        };
    }
}
