package lab.healthcare.minihis;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.UUID;

@Component
public class SecurityEvents {
    private final JdbcTemplate jdbc;

    public SecurityEvents(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS security_event (
                    event_id INTEGER PRIMARY KEY,
                    actor TEXT NOT NULL,
                    role TEXT NOT NULL,
                    organization_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    resource TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    correlation TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                )
                """);
    }

    public void record(String actor, String role, String organizationId, String action, String resource, String outcome) {
        String safeActor = clean(actor);
        String safeRole = clean(role);
        String safeOrganization = clean(organizationId);
        String safeAction = clean(action);
        String safeResource = clean(resource);
        String safeOutcome = clean(outcome);
        if (safeActor.contains("eyJ") || safeResource.contains("eyJ")) {
            return;
        }
        jdbc.update("""
                INSERT INTO security_event (
                    actor, role, organization_id, action, resource, outcome, correlation, recorded_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                safeActor, safeRole, safeOrganization, safeAction, safeResource, safeOutcome,
                UUID.randomUUID().toString(), OffsetDateTime.now(ZoneOffset.UTC).toString());
    }

    private static String clean(String value) {
        String text = value == null ? "" : value;
        text = text.replaceAll("[\\r\\n\\t]", " ");
        return text.length() > 80 ? text.substring(0, 80) : text;
    }
}
