package lab.healthcare.fhir.aiconsumerreadiness;

import lab.healthcare.fhir.aiconsumer.AiConsumerDispatchStatus;
import lab.healthcare.fhir.aiconsumerpolicy.AiConsumerPolicyDecision;
import lab.healthcare.fhir.firstai.FirstAiProcessingStatus;

/**
 * Readiness verdict. Never includes tokens, Patient identifiers, or FHIR JSON.
 * Ready for a future handoff is not handoff authorization and not dispatch.
 */
public record AiConsumerReadinessResult(
        AiConsumerReadinessStatus readinessStatus,
        String reasonCode,
        AiConsumerPolicyDecision policyDecision,
        String contractVersion,
        String requestedOperation,
        String requestedScope,
        String consumerType,
        boolean modelCallAuthorized,
        boolean modelCalled,
        FirstAiProcessingStatus processingStatus,
        AiConsumerDispatchStatus dispatchStatus,
        boolean requiresHumanReview,
        boolean handoffAuthorized,
        boolean dispatchPerformed) {

    public AiConsumerReadinessResult {
        if (readinessStatus == null) {
            throw new IllegalArgumentException("AI consumer readiness status must be provided");
        }
        if (processingStatus == null) {
            throw new IllegalArgumentException("AI consumer readiness processing status must be provided");
        }
        if (dispatchStatus == null) {
            throw new IllegalArgumentException("AI consumer readiness dispatch status must be provided");
        }
        if (processingStatus != FirstAiProcessingStatus.NOT_EXECUTED) {
            throw new IllegalArgumentException("AI consumer readiness must not execute model processing");
        }
        if (dispatchStatus != AiConsumerDispatchStatus.NOT_DISPATCHED) {
            throw new IllegalArgumentException("AI consumer readiness must not dispatch");
        }
        if (modelCalled) {
            throw new IllegalArgumentException("AI consumer readiness must not call a model");
        }
        if (modelCallAuthorized) {
            throw new IllegalArgumentException("AI consumer readiness must not authorize a model call");
        }
        if (!requiresHumanReview) {
            throw new IllegalArgumentException("AI consumer readiness requires human review");
        }
        if (handoffAuthorized) {
            throw new IllegalArgumentException("AI consumer readiness must not authorize handoff");
        }
        if (dispatchPerformed) {
            throw new IllegalArgumentException("AI consumer readiness must not perform dispatch");
        }
        reasonCode = blankToEmpty(reasonCode);
        contractVersion = blankToEmpty(contractVersion);
        requestedOperation = blankToEmpty(requestedOperation);
        requestedScope = blankToEmpty(requestedScope);
        consumerType = blankToEmpty(consumerType);
    }

    @Override
    public String toString() {
        return "AiConsumerReadinessResult[readinessStatus="
                + readinessStatus
                + ", reasonCode="
                + reasonCode
                + ", policyDecision="
                + policyDecision
                + ", contractVersion="
                + contractVersion
                + ", requestedOperation="
                + requestedOperation
                + ", requestedScope="
                + requestedScope
                + ", consumerType="
                + consumerType
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
                + ", handoffAuthorized="
                + handoffAuthorized
                + ", dispatchPerformed="
                + dispatchPerformed
                + "]";
    }

    private static String blankToEmpty(String value) {
        return value == null ? "" : value.trim();
    }
}
