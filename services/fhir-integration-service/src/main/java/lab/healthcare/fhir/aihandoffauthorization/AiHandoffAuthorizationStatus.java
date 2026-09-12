package lab.healthcare.fhir.aihandoffauthorization;

/**
 * Effective handoff-authorization verdict. Task 064 never authorizes handoff.
 */
public enum AiHandoffAuthorizationStatus {
    HANDOFF_NOT_AUTHORIZED,
    BLOCKED,
    HUMAN_REVIEW_REQUIRED,
    NOT_READY_FOR_AUTHORIZATION
}
