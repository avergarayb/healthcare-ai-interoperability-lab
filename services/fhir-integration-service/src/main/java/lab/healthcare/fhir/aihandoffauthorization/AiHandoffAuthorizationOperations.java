package lab.healthcare.fhir.aihandoffauthorization;

/**
 * Conceptual authorization operations. Only {@link #EVALUATE_HANDOFF_AUTHORIZATION}
 * exists. It evaluates the boundary; it does not authorize or send anything.
 */
public final class AiHandoffAuthorizationOperations {

    public static final String EVALUATE_HANDOFF_AUTHORIZATION = "EVALUATE_HANDOFF_AUTHORIZATION";

    private AiHandoffAuthorizationOperations() {
    }
}
