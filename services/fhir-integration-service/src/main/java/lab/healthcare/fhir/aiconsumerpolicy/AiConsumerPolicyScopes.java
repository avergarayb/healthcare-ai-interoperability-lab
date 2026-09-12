package lab.healthcare.fhir.aiconsumerpolicy;

/**
 * Synthetic consumer scopes. Only {@link #CONTRACT_READ} is allowed.
 */
public final class AiConsumerPolicyScopes {

    public static final String CONTRACT_READ = "ai.contract.read";

    private AiConsumerPolicyScopes() {
    }
}
