package lab.healthcare.fhir.aiconsumerreadiness;

/**
 * Technical readiness for a future handoff. Ready is not authorization and
 * not dispatch.
 */
public enum AiConsumerReadinessStatus {
    READY_FOR_FUTURE_HANDOFF,
    BLOCKED,
    HUMAN_REVIEW_REQUIRED,
    NOT_READY
}
