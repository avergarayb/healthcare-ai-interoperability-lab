package lab.healthcare.fhir.aiconsumerpolicy;

/**
 * Policy verdict. Allowed future consumption is not model authorization and
 * not dispatch.
 */
public enum AiConsumerPolicyDecision {
    ALLOWED_FOR_FUTURE_CONSUMPTION,
    REJECTED,
    HUMAN_REVIEW_REQUIRED
}
