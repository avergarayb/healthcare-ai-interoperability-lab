package lab.healthcare.fhir.aiconsumerpolicy;

import lab.healthcare.fhir.aiconsumer.AiConsumerDispatchStatus;
import lab.healthcare.fhir.firstai.FirstAiProcessingStatus;

/**
 * Policy verdict. Never includes tokens, Patient identifiers, or FHIR JSON.
 */
public record AiConsumerPolicyResult(
        AiConsumerPolicyDecision decision,
        String reasonCode,
        String contractVersion,
        String consumerType,
        String requestedOperation,
        String requestedScope,
        boolean modelCallAuthorized,
        boolean modelCalled,
        FirstAiProcessingStatus processingStatus,
        AiConsumerDispatchStatus dispatchStatus,
        boolean requiresHumanReview) {

    public AiConsumerPolicyResult {
        if (decision == null) {
            throw new IllegalArgumentException("AI consumer policy decision must be provided");
        }
        if (processingStatus == null) {
            throw new IllegalArgumentException("AI consumer policy processing status must be provided");
        }
        if (dispatchStatus == null) {
            throw new IllegalArgumentException("AI consumer policy dispatch status must be provided");
        }
        if (processingStatus != FirstAiProcessingStatus.NOT_EXECUTED) {
            throw new IllegalArgumentException("AI consumer policy must not execute model processing");
        }
        if (dispatchStatus != AiConsumerDispatchStatus.NOT_DISPATCHED) {
            throw new IllegalArgumentException("AI consumer policy must not dispatch");
        }
        if (modelCalled) {
            throw new IllegalArgumentException("AI consumer policy must not call a model");
        }
        if (modelCallAuthorized) {
            throw new IllegalArgumentException(AiConsumerPolicyReasonCodes.PREMATURE_MODEL_AUTHORIZATION);
        }
        if (!requiresHumanReview) {
            throw new IllegalArgumentException("AI consumer policy requires human review");
        }
        reasonCode = blankToEmpty(reasonCode);
        contractVersion = blankToEmpty(contractVersion);
        consumerType = blankToEmpty(consumerType);
        requestedOperation = blankToEmpty(requestedOperation);
        requestedScope = blankToEmpty(requestedScope);
    }

    @Override
    public String toString() {
        return "AiConsumerPolicyResult[decision="
                + decision
                + ", reasonCode="
                + reasonCode
                + ", contractVersion="
                + contractVersion
                + ", consumerType="
                + consumerType
                + ", requestedOperation="
                + requestedOperation
                + ", requestedScope="
                + requestedScope
                + ", modelCallAuthorized="
                + modelCallAuthorized
                + ", modelCalled="
                + modelCalled
                + ", processingStatus="
                + processingStatus
                + ", dispatchStatus="
                + dispatchStatus
                + ", requiresHumanReview="
                + requiresHumanReview
                + "]";
    }

    private static String blankToEmpty(String value) {
        return value == null ? "" : value.trim();
    }
}
