package lab.healthcare.fhir.firstai;

import lab.healthcare.fhir.agent.AgentDecision;

/**
 * Technical status of the first isolated AI component. Not a clinical
 * diagnosis and not a model answer.
 */
public enum FirstAiComponentStatus {
    PREPARED,
    BLOCKED,
    REQUIRES_HUMAN_REVIEW;

    public static FirstAiComponentStatus from(AgentDecision decision) {
        if (decision == null) {
            throw new IllegalArgumentException("First AI component requires an agent decision");
        }
        return switch (decision) {
            case READY -> PREPARED;
            case BLOCKED -> BLOCKED;
            case REQUIRES_HUMAN_REVIEW -> REQUIRES_HUMAN_REVIEW;
        };
    }
}
