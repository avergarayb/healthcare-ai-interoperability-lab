package lab.healthcare.fhir.aiconsumerconsent;

import lab.healthcare.fhir.aiconsumerauthorization.AiConsumerAuthorizationResult;

/**
 * Deny-by-default consumer consent and purpose boundary. Authentication is
 * not authorization. Authorization is not consent. Consent is not purpose
 * approval. Purpose is not clinical access. Task 066 never grants any of
 * those.
 */
public final class AiConsumerConsentBoundary {

    private AiConsumerConsentBoundary() {
    }

    public static AiConsumerConsentResult evaluate(AiConsumerAuthorizationResult authorization) {
        if (authorization == null) {
            return missingAuthorization();
        }
        return evaluate(AiConsumerConsentInput.from(authorization));
    }

    public static AiConsumerConsentResult evaluate(
            AiConsumerAuthorizationResult authorization, ConsumerConsentContext consent) {
        if (authorization == null) {
            return missingAuthorization();
        }
        return evaluate(AiConsumerConsentInput.of(authorization, consent));
    }

    public static AiConsumerConsentResult evaluate(AiConsumerConsentInput input) {
        if (input == null || !input.authorizationResultPresent()) {
            return missingAuthorization();
        }
        ConsumerConsentContext consent =
                input.consent() == null ? ConsumerConsentContext.laboratory() : input.consent();
        if (input.authorizationGranted() || input.consumerAuthorizationAvailable()) {
            return result(
                    AiConsumerConsentStatus.BLOCKED,
                    AiConsumerConsentReasonCodes.UNEXPECTED_CONSUMER_AUTHORIZATION,
                    consent);
        }
        if (consent.consentVerified() && !consent.consentProviderConfigured()) {
            return result(
                    AiConsumerConsentStatus.BLOCKED,
                    AiConsumerConsentReasonCodes.UNTRUSTED_CONSENT_ASSERTION,
                    consent);
        }
        if (consent.purposeApproved() && !consent.consentProviderConfigured()) {
            return result(
                    AiConsumerConsentStatus.BLOCKED,
                    AiConsumerConsentReasonCodes.UNTRUSTED_PURPOSE_ASSERTION,
                    consent);
        }
        if (consent.dataScopeApproved() && !consent.consentProviderConfigured()) {
            return result(
                    AiConsumerConsentStatus.BLOCKED,
                    AiConsumerConsentReasonCodes.UNTRUSTED_DATA_SCOPE_ASSERTION,
                    consent);
        }
        if (!consent.contextPresent()) {
            return result(
                    AiConsumerConsentStatus.CONSENT_NOT_IMPLEMENTED,
                    AiConsumerConsentReasonCodes.MISSING_CONSENT_CONTEXT,
                    consent);
        }
        if (!consent.tenantContextPresent()) {
            return result(
                    AiConsumerConsentStatus.BLOCKED,
                    AiConsumerConsentReasonCodes.MISSING_TENANT_CONTEXT,
                    consent);
        }
        if (consent.consentReferencePresent() && !consent.consentVerified()) {
            return result(
                    AiConsumerConsentStatus.CONSENT_NOT_IMPLEMENTED,
                    AiConsumerConsentReasonCodes.CONSENT_REFERENCE_NOT_VERIFIED,
                    consent);
        }
        if (!consent.purposeDeclared() || consent.requestedPurpose() == ConsumerConsentPurpose.UNKNOWN) {
            return result(
                    AiConsumerConsentStatus.PURPOSE_NOT_VERIFIED,
                    purposeMissingReason(consent),
                    consent);
        }
        if (consent.requestedDataScope().isEmpty()) {
            return result(
                    AiConsumerConsentStatus.DATA_SCOPE_NOT_VERIFIED,
                    AiConsumerConsentReasonCodes.MISSING_DATA_SCOPE,
                    consent);
        }
        if (!consent.humanReviewCompleted()) {
            return result(
                    AiConsumerConsentStatus.HUMAN_REVIEW_REQUIRED,
                    AiConsumerConsentReasonCodes.HUMAN_REVIEW_NOT_COMPLETED,
                    consent);
        }
        if (!input.consumerAuthorizationAvailable()) {
            return result(
                    AiConsumerConsentStatus.CONSENT_NOT_IMPLEMENTED,
                    AiConsumerConsentReasonCodes.CONSUMER_AUTHORIZATION_NOT_AVAILABLE,
                    consent);
        }
        return result(
                AiConsumerConsentStatus.CONSENT_NOT_IMPLEMENTED,
                AiConsumerConsentReasonCodes.PURPOSE_NOT_APPROVED,
                consent);
    }

    private static String purposeMissingReason(ConsumerConsentContext consent) {
        if (consent.requestedPurpose() == ConsumerConsentPurpose.UNKNOWN && consent.purposeDeclared()) {
            return AiConsumerConsentReasonCodes.UNKNOWN_OR_MISSING_PURPOSE;
        }
        return AiConsumerConsentReasonCodes.MISSING_PURPOSE;
    }

    private static AiConsumerConsentResult missingAuthorization() {
        return result(
                AiConsumerConsentStatus.BLOCKED,
                AiConsumerConsentReasonCodes.MISSING_CONSUMER_AUTHORIZATION_RESULT,
                ConsumerConsentContext.laboratory());
    }

    private static AiConsumerConsentResult result(
            AiConsumerConsentStatus status, String reason, ConsumerConsentContext consent) {
        return new AiConsumerConsentResult(
                status,
                reason,
                AiConsumerConsentOperations.EVALUATE_CONSUMER_CONSENT,
                consent.requestedPurpose().name(),
                consent.requestedDataScope(),
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                AiConsumerConsentResult.NOT_EXECUTED,
                AiConsumerConsentResult.NOT_DISPATCHED,
                true);
    }
}
