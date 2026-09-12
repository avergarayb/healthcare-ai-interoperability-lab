package lab.healthcare.fhir.aiconsumerconsent;

import lab.healthcare.fhir.aiconsumerauthorization.AiConsumerAuthorizationResult;

/**
 * Consent input copied from a consumer-authorization result plus a synthetic
 * consent context. Unlike the 065 result, this record may hold
 * {@code authorizationGranted=true} or {@code consumerAuthorizationAvailable=true}
 * so the boundary can detect those flags instead of silently accepting them.
 */
public record AiConsumerConsentInput(
        boolean authorizationResultPresent,
        boolean authorizationGranted,
        boolean consumerAuthorizationAvailable,
        boolean requiresHumanReview,
        ConsumerConsentContext consent) {

    public static AiConsumerConsentInput from(AiConsumerAuthorizationResult authorization) {
        if (authorization == null) {
            return null;
        }
        return new AiConsumerConsentInput(
                true,
                authorization.authorizationGranted(),
                authorization.consumerAuthorizationAvailable(),
                authorization.requiresHumanReview(),
                ConsumerConsentContext.laboratory());
    }

    public static AiConsumerConsentInput of(
            AiConsumerAuthorizationResult authorization, ConsumerConsentContext consent) {
        if (authorization == null) {
            return null;
        }
        return new AiConsumerConsentInput(
                true,
                authorization.authorizationGranted(),
                authorization.consumerAuthorizationAvailable(),
                authorization.requiresHumanReview(),
                consent == null ? ConsumerConsentContext.laboratory() : consent);
    }

    public AiConsumerConsentInput withAuthorizationGranted(boolean value) {
        return new AiConsumerConsentInput(
                authorizationResultPresent,
                value,
                consumerAuthorizationAvailable,
                requiresHumanReview,
                consent);
    }

    public AiConsumerConsentInput withConsumerAuthorizationAvailable(boolean value) {
        return new AiConsumerConsentInput(
                authorizationResultPresent,
                authorizationGranted,
                value,
                requiresHumanReview,
                consent);
    }
}
