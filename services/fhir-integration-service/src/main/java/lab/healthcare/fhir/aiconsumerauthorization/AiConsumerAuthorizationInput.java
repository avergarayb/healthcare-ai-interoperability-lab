package lab.healthcare.fhir.aiconsumerauthorization;

import lab.healthcare.fhir.aihandoffauthorization.AiHandoffAuthorizationResult;

/**
 * Authorization input copied from a handoff-authorization result plus a
 * synthetic security context. Unlike the 064 result, this record may hold
 * {@code handoffAuthorized=true} so the boundary can detect it instead of
 * silently accepting it.
 */
public record AiConsumerAuthorizationInput(
        boolean handoffResultPresent,
        boolean handoffAuthorized,
        boolean dispatchPerformed,
        boolean externalAuthorizationAvailable,
        boolean modelCallAuthorized,
        boolean modelCalled,
        boolean requiresHumanReview,
        ConsumerSecurityContext security) {

    public static AiConsumerAuthorizationInput from(AiHandoffAuthorizationResult handoff) {
        if (handoff == null) {
            return null;
        }
        return new AiConsumerAuthorizationInput(
                true,
                handoff.handoffAuthorized(),
                handoff.dispatchPerformed(),
                handoff.externalAuthorizationAvailable(),
                handoff.modelCallAuthorized(),
                handoff.modelCalled(),
                handoff.requiresHumanReview(),
                ConsumerSecurityContext.laboratory());
    }

    public static AiConsumerAuthorizationInput of(
            AiHandoffAuthorizationResult handoff, ConsumerSecurityContext security) {
        if (handoff == null) {
            return null;
        }
        return new AiConsumerAuthorizationInput(
                true,
                handoff.handoffAuthorized(),
                handoff.dispatchPerformed(),
                handoff.externalAuthorizationAvailable(),
                handoff.modelCallAuthorized(),
                handoff.modelCalled(),
                handoff.requiresHumanReview(),
                security == null ? ConsumerSecurityContext.laboratory() : security);
    }

    public AiConsumerAuthorizationInput withHandoffAuthorized(boolean value) {
        return new AiConsumerAuthorizationInput(
                handoffResultPresent,
                value,
                dispatchPerformed,
                externalAuthorizationAvailable,
                modelCallAuthorized,
                modelCalled,
                requiresHumanReview,
                security);
    }
}
