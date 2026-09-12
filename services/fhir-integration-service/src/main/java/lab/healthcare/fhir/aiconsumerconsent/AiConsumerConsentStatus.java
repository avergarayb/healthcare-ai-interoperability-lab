package lab.healthcare.fhir.aiconsumerconsent;

/**
 * Consent and purpose verdict. Task 066 never grants consent, purpose
 * approval, clinical access, handoff, or dispatch.
 */
public enum AiConsumerConsentStatus {
    CONSENT_NOT_IMPLEMENTED,
    PURPOSE_NOT_VERIFIED,
    DATA_SCOPE_NOT_VERIFIED,
    BLOCKED,
    HUMAN_REVIEW_REQUIRED,
    NOT_ELIGIBLE_FOR_CONSUMPTION
}
