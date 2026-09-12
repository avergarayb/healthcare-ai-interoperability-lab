package lab.healthcare.fhir.aihandoffauthorization;

import lab.healthcare.fhir.aiconsumerpolicy.AiConsumerPolicyDecision;
import lab.healthcare.fhir.aiconsumerreadiness.AiConsumerReadinessResult;
import lab.healthcare.fhir.aiconsumerreadiness.AiConsumerReadinessStatus;

/**
 * Authorization input copied from a readiness result. Unlike
 * {@link AiConsumerReadinessResult}, this record may hold inconsistent
 * security flags so the boundary can detect them instead of silently
 * correcting them.
 */
public record AiHandoffAuthorizationInput(
        AiConsumerReadinessStatus readinessStatus,
        AiConsumerPolicyDecision policyDecision,
        String contractVersion,
        String requestedOperation,
        String requestedScope,
        String consumerType,
        boolean modelCallAuthorized,
        boolean modelCalled,
        String processingStatus,
        String dispatchStatus,
        boolean requiresHumanReview,
        boolean handoffAuthorized,
        boolean dispatchPerformed,
        boolean consumerIdentityPresent,
        boolean consumerAuthenticated,
        boolean consumerAuthorized,
        boolean tenantContextPresent,
        boolean externalAuthorizationAvailable,
        String requestedHandoffScope) {

    public static AiHandoffAuthorizationInput from(AiConsumerReadinessResult readiness) {
        if (readiness == null) {
            return null;
        }
        boolean identityPresent = readiness.consumerType() != null && !readiness.consumerType().isBlank();
        boolean syntheticallyReady = readiness.readinessStatus() == AiConsumerReadinessStatus.READY_FOR_FUTURE_HANDOFF;
        return new AiHandoffAuthorizationInput(
                readiness.readinessStatus(),
                readiness.policyDecision(),
                readiness.contractVersion(),
                readiness.requestedOperation(),
                readiness.requestedScope(),
                readiness.consumerType(),
                readiness.modelCallAuthorized(),
                readiness.modelCalled(),
                readiness.processingStatus() == null ? "" : readiness.processingStatus().name(),
                readiness.dispatchStatus() == null ? "" : readiness.dispatchStatus().name(),
                readiness.requiresHumanReview(),
                readiness.handoffAuthorized(),
                readiness.dispatchPerformed(),
                identityPresent,
                syntheticallyReady,
                syntheticallyReady,
                syntheticallyReady,
                false,
                "");
    }
}
