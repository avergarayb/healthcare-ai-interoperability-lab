package lab.healthcare.fhir.smart;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.time.Clock;
import java.time.Instant;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;

/**
 * Process-local pending sessions. Not Redis and not a durable auth store.
 */
@Component
public class InMemoryAuthorizationSessionStore implements AuthorizationSessionStore {

    private final ConcurrentMap<String, PendingAuthorizationSession> sessions = new ConcurrentHashMap<>();
    private final Clock clock;

    @Autowired
    public InMemoryAuthorizationSessionStore() {
        this(Clock.systemUTC());
    }

    public InMemoryAuthorizationSessionStore(Clock clock) {
        this.clock = clock == null ? Clock.systemUTC() : clock;
    }

    @Override
    public void save(PendingAuthorizationSession session) {
        if (session == null || session.state() == null || session.state().isBlank()) {
            throw new IllegalArgumentException("Pending authorization session must include state");
        }
        sessions.put(session.state(), session);
    }

    @Override
    public PendingAuthorizationSession consume(String state) {
        if (state == null || state.isBlank()) {
            throw new SmartAuthorizationException("SMART authorization failed: missing state");
        }
        PendingAuthorizationSession session = sessions.remove(state.trim());
        if (session == null) {
            throw new SmartAuthorizationException("SMART authorization failed: unknown or expired session");
        }
        if (session.isExpiredAt(Instant.now(clock))) {
            throw new SmartAuthorizationException("SMART authorization failed: unknown or expired session");
        }
        return session;
    }
}
