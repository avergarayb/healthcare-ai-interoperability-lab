package lab.healthcare.fhir.agent;

/**
 * Programming error when the agent is invoked without an authorized input.
 * Business blocks are returned as {@link DeterministicAgentResult}, not thrown.
 */
public class AgentValidationException extends RuntimeException {

    public AgentValidationException(String message) {
        super(message);
    }
}
