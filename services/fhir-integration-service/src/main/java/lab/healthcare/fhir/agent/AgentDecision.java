package lab.healthcare.fhir.agent;

/**
 * Deterministic boundary verdict. Not a clinical diagnosis and not an LLM
 * answer.
 */
public enum AgentDecision {
    READY,
    BLOCKED,
    REQUIRES_HUMAN_REVIEW
}
