package lab.healthcare.fhir.smart;

/**
 * Stores one pending SMART session keyed by {@code state}. Consume is terminal.
 */
public interface AuthorizationSessionStore {

    void save(PendingAuthorizationSession session);

    PendingAuthorizationSession consume(String state);
}
