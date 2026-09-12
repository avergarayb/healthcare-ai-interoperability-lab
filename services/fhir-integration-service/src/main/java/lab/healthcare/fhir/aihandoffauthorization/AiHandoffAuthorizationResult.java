package lab.healthcare.fhir.aihandoffauthorization;

import lab.healthcare.fhir.aiconsumer.AiConsumerDispatchStatus;
import lab.healthcare.fhir.aiconsumerpolicy.AiConsumerPolicyDecision;
import lab.healthcare.fhir.aiconsumerreadiness.AiConsumerReadinessStatus;
import lab.healthcare.fhir.firstai.FirstAiProcessingStatus;

/**
 * Handoff-authorization verdict. Never includes tokens, Patient identifiers,
 * or FHIR JSON. Ready for a future handoff is not authorization and not dispatch.
 */
public record AiHandoffAuthorizationResult(
        AiHandoffAuthorizationStatus authorizationStatus,
        String reasonCode,
        AiConsumerReadinessStatus readinessStatus,
        AiConsumerPolicyDecision policyDecision,
        String contractVersion,
        String requestedOperation,
        String requestedScope,
        String consumerType,
        boolean consumerIdentityPresent,
        boolean consumerAuthenticated,
        boolean consumerAuthorized,
        boolean tenantContextPresent,
        boolean externalAuthorizationAvailable,
        boolean handoffAuthorized,
        boolean dispatchPerformed,
        boolean modelCallAuthorized,
        boolean modelCalled,
        FirstAiProcessingStatus processingStatus,
        AiConsumerDispatchStatus dispatchStatus,
        boolean requiresHumanReview) {

    public AiHandoffAuthorizationResult {
        if (authorizationStatus == null) {
            throw new IllegalArgumentException("AI handoff authorization status must be provided");
        }
        if (processingStatus == null) {
            throw new IllegalArgumentException("AI handoff authorization processing status must be provided");
        }
        if (dispatchStatus == null) {
            throw new IllegalArgumentException("AI handoff authorization dispatch status must be provided");
        }
        if (processingStatus != FirstAiProcessingStatus.NOT_EXECUTED) {
            throw new IllegalArgumentException("AI handoff authorization must not execute model processing");
        }
        if (dispatchStatus != AiConsumerDispatchStatus.NOT_DISPATCHED) {
            throw new IllegalArgumentException("AI handoff authorization must not dispatch");
        }
        if (modelCalled) {
            throw new IllegalArgumentException("AI handoff authorization must not call a model");
        }
        if (modelCallAuthorized) {
            throw new IllegalArgumentException("AI handoff authorization must not authorize a model call");
        }
        if (!requiresHumanReview) {
            throw new IllegalArgumentException("AI handoff authorization requires human review");
        }
        if (handoffAuthorized) {
            throw new IllegalArgumentException("AI handoff authorization must not authorize handoff");
        }
        if (dispatchPerformed) {
            throw new IllegalArgumentException("AI handoff authorization must not perform dispatch");
        }
        if (externalAuthorizationAvailable) {
            throw new IllegalArgumentException("AI handoff authorization has no external authorization");
        }
        reasonCode = blankToEmpty(reasonCode);
        contractVersion = blankToEmpty(contractVersion);
        requestedOperation = blankToEmpty(requestedOperation);
        requestedScope = blankToEmpty(requestedScope);
        consumerType = blankToEmpty(consumerType);
    }

    @Override
    public String toString() {
        return "AiHandoffAuthorizationResult[authorizationStatus="
                + authorizationStatus
                + ", reasonCode="
                + reasonCode
                + ", readinessStatus="
                + readinessStatus
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
                + ", consumerIdentityPresent="
                + consumerIdentityPresent
                + ", consumerAuthenticated="
                + consumerAuthenticated
                + ", consumerAuthorized="
                + consumerAuthorized
                + ", tenantContextPresent="
                + tenantContextPresent
                + ", externalAuthorizationAvailable="
                + externalAuthorizationAvailable
                + ", handoffAuthorized="
                + handoffAuthorized
                + ", dispatchPerformed="
                + dispatchPerformed
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
