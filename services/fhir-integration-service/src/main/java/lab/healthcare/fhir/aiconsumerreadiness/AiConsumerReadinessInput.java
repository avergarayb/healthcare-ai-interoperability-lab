package lab.healthcare.fhir.aiconsumerreadiness;

import lab.healthcare.fhir.aiconsumerpolicy.AiConsumerPolicyDecision;
import lab.healthcare.fhir.aiconsumerpolicy.AiConsumerPolicyResult;

/**
 * Readiness input copied from a policy result. Unlike
 * {@link AiConsumerPolicyResult}, this record may hold inconsistent security
 * flags so readiness can detect them instead of silently correcting them.
 */
public record AiConsumerReadinessInput(
        AiConsumerPolicyDecision policyDecision,
        String contractVersion,
        String consumerType,
        String requestedOperation,
        String requestedScope,
        boolean modelCallAuthorized,
        boolean modelCalled,
        String processingStatus,
        String dispatchStatus,
        boolean requiresHumanReview) {

    public static AiConsumerReadinessInput from(AiConsumerPolicyResult policy) {
        if (policy == null) {
            return null;
        }
        return new AiConsumerReadinessInput(
                policy.decision(),
                policy.contractVersion(),
                policy.consumerType(),
                policy.requestedOperation(),
                policy.requestedScope(),
                policy.modelCallAuthorized(),
                policy.modelCalled(),
                policy.processingStatus() == null ? "" : policy.processingStatus().name(),
                policy.dispatchStatus() == null ? "" : policy.dispatchStatus().name(),
                policy.requiresHumanReview());
    }
}
