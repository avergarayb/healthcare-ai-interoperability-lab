package lab.healthcare.fhir.aiconsumerauthorization;

/**
 * Consumer authentication and authorization verdict. Task 065 never grants
 * authorization, handoff, or dispatch.
 */
public enum AiConsumerAuthorizationStatus {
    AUTHORIZATION_NOT_IMPLEMENTED,
    BLOCKED,
    HUMAN_REVIEW_REQUIRED,
    NOT_AUTHENTICATED,
    NOT_AUTHORIZED
}
