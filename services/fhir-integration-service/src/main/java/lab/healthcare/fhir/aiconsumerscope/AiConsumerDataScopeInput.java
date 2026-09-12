package lab.healthcare.fhir.aiconsumerscope;

import lab.healthcare.fhir.aiconsumerconsent.AiConsumerConsentResult;

/**
 * Data-scope input copied from a consent result plus a synthetic scope
 * context. Unlike the 066 result, this record may hold
 * {@code consentAvailable=true} or {@code purposeApproved=true} so the
 * boundary can detect those flags instead of silently accepting them.
 */
public record AiConsumerDataScopeInput(
        boolean consentResultPresent,
        boolean consentAvailable,
        boolean consentVerified,
        boolean purposeApproved,
        boolean dataScopeApproved,
        boolean clinicalDataAccessAllowed,
        boolean requiresHumanReview,
        String requestedPurpose,
        ConsumerDataScopeContext scope) {

    public static AiConsumerDataScopeInput from(AiConsumerConsentResult consent) {
        if (consent == null) {
            return null;
        }
        return new AiConsumerDataScopeInput(
                true,
                consent.consentAvailable(),
                consent.consentVerified(),
                consent.purposeApproved(),
                consent.dataScopeApproved(),
                consent.clinicalDataAccessAllowed(),
                consent.requiresHumanReview(),
                consent.requestedPurpose(),
                ConsumerDataScopeContext.laboratory());
    }

    public static AiConsumerDataScopeInput of(
            AiConsumerConsentResult consent, ConsumerDataScopeContext scope) {
        if (consent == null) {
            return null;
        }
        return new AiConsumerDataScopeInput(
                true,
                consent.consentAvailable(),
                consent.consentVerified(),
                consent.purposeApproved(),
                consent.dataScopeApproved(),
                consent.clinicalDataAccessAllowed(),
                consent.requiresHumanReview(),
                consent.requestedPurpose(),
                scope == null ? ConsumerDataScopeContext.laboratory() : scope);
    }

    public AiConsumerDataScopeInput withConsentAvailable(boolean value) {
        return new AiConsumerDataScopeInput(
                consentResultPresent,
                value,
                consentVerified,
                purposeApproved,
                dataScopeApproved,
                clinicalDataAccessAllowed,
                requiresHumanReview,
                requestedPurpose,
                scope);
    }

    public AiConsumerDataScopeInput withPurposeApproved(boolean value) {
        return new AiConsumerDataScopeInput(
                consentResultPresent,
                consentAvailable,
                consentVerified,
                value,
                dataScopeApproved,
                clinicalDataAccessAllowed,
                requiresHumanReview,
                requestedPurpose,
                scope);
    }
}
