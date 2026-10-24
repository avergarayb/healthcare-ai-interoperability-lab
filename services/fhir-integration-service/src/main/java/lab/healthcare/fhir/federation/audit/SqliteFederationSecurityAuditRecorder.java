package lab.healthcare.fhir.federation.audit;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * Local append-only application sink for federation access decisions.
 * The file is durable across process restarts but is not tamper-proof.
 */
public final class SqliteFederationSecurityAuditRecorder implements FederationSecurityAuditRecorder {

    private static final Logger log = LoggerFactory.getLogger(SqliteFederationSecurityAuditRecorder.class);
    private static final int SCHEMA_VERSION = 1;
    private static final String METADATA_JSON = "{\"route\":\"/api/clinical-federation/v1/context\"}";

    private final Path path;
    private final String jdbcUrl;

    public SqliteFederationSecurityAuditRecorder(Path path) {
        if (path == null) {
            throw new IllegalArgumentException("Federation security audit path is required");
        }
        this.path = path.toAbsolutePath().normalize();
        this.jdbcUrl = "jdbc:sqlite:" + this.path;
        initialize();
    }

    @Override
    public synchronized void append(FederationSecurityAuditEvent event) {
        FederationSecurityAuditEvent validated = requireEvent(event);
        try (Connection connection = open()) {
            connection.setAutoCommit(false);
            try (PreparedStatement statement = connection.prepareStatement(
                    """
                    INSERT INTO federation_security_audit_events (
                        event_id, timestamp_utc, event_type, source_service,
                        actor_type, actor_id, organization_id, action,
                        resource_type, resource_reference, outcome, reason_code,
                        correlation_id, metadata_json, contract_version)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """)) {
                statement.setString(1, validated.eventId());
                statement.setString(2, validated.timestampUtc().toString());
                statement.setString(3, validated.eventType());
                statement.setString(4, validated.sourceService());
                statement.setString(5, validated.actorType());
                statement.setString(6, validated.actorId());
                statement.setString(7, validated.organizationId());
                statement.setString(8, validated.action());
                statement.setString(9, validated.resourceType());
                statement.setString(10, validated.resourceReference());
                statement.setString(11, validated.outcome());
                statement.setString(12, validated.reasonCode());
                statement.setString(13, validated.correlationId());
                statement.setString(14, METADATA_JSON);
                statement.setString(15, validated.contractVersion());
                statement.executeUpdate();
                connection.commit();
            } catch (RuntimeException | SQLException ex) {
                rollback(connection);
                throw ex;
            }
        } catch (SQLException | RuntimeException ex) {
            if (ex instanceof FederationSecurityAuditUnavailable unavailable) {
                throw unavailable;
            }
            throw new FederationSecurityAuditUnavailable(ex);
        }
        log.info(
                "SECURITY_AUDIT eventId={} eventType={} sourceService={} actorType={} actorId={} organizationId={} action={} resourceType={} resourceReference={} outcome={} reasonCode={} correlationId={} contractVersion={}",
                validated.eventId(),
                validated.eventType(),
                validated.sourceService(),
                validated.actorType(),
                validated.actorId(),
                validated.organizationId() == null ? "" : validated.organizationId(),
                validated.action(),
                validated.resourceType(),
                validated.resourceReference(),
                validated.outcome(),
                validated.reasonCode(),
                validated.correlationId(),
                validated.contractVersion());
    }

    synchronized List<FederationSecurityAuditEvent> recorded() {
        try (Connection connection = open();
                PreparedStatement statement = connection.prepareStatement(
                        "SELECT * FROM federation_security_audit_events ORDER BY rowid");
                ResultSet rows = statement.executeQuery()) {
            List<FederationSecurityAuditEvent> events = new ArrayList<>();
            while (rows.next()) {
                if (!METADATA_JSON.equals(rows.getString("metadata_json"))) {
                    throw new FederationSecurityAuditUnavailable();
                }
                events.add(new FederationSecurityAuditEvent(
                        rows.getString("event_id"),
                        Instant.parse(rows.getString("timestamp_utc")),
                        rows.getString("event_type"),
                        rows.getString("source_service"),
                        rows.getString("actor_type"),
                        rows.getString("actor_id"),
                        rows.getString("organization_id"),
                        rows.getString("action"),
                        rows.getString("resource_type"),
                        rows.getString("resource_reference"),
                        rows.getString("outcome"),
                        rows.getString("reason_code"),
                        rows.getString("correlation_id"),
                        Map.of("route", FederationSecurityAuditEvent.ROUTE),
                        rows.getString("contract_version")));
            }
            return List.copyOf(events);
        } catch (SQLException | RuntimeException ex) {
            if (ex instanceof FederationSecurityAuditUnavailable unavailable) {
                throw unavailable;
            }
            throw new FederationSecurityAuditUnavailable(ex);
        }
    }

    private void initialize() {
        try {
            Path parent = path.getParent();
            if (parent != null) {
                Files.createDirectories(parent);
            }
            try (Connection connection = open(); Statement statement = connection.createStatement()) {
                try (ResultSet row = statement.executeQuery("PRAGMA journal_mode=WAL")) {
                    if (!row.next() || !"wal".equalsIgnoreCase(row.getString(1))) {
                        throw new FederationSecurityAuditUnavailable();
                    }
                }
                int version;
                try (ResultSet row = statement.executeQuery("PRAGMA user_version")) {
                    version = row.next() ? row.getInt(1) : -1;
                }
                if (version == 0) {
                    statement.execute("""
                            CREATE TABLE federation_security_audit_events (
                                event_id TEXT PRIMARY KEY,
                                timestamp_utc TEXT NOT NULL,
                                event_type TEXT NOT NULL,
                                source_service TEXT NOT NULL,
                                actor_type TEXT NOT NULL,
                                actor_id TEXT NOT NULL,
                                organization_id TEXT,
                                action TEXT NOT NULL,
                                resource_type TEXT NOT NULL,
                                resource_reference TEXT NOT NULL,
                                outcome TEXT NOT NULL,
                                reason_code TEXT NOT NULL,
                                correlation_id TEXT NOT NULL,
                                metadata_json TEXT NOT NULL,
                                contract_version TEXT NOT NULL)
                            """);
                    statement.execute("CREATE INDEX federation_security_audit_correlation_idx "
                            + "ON federation_security_audit_events (correlation_id)");
                    statement.execute("PRAGMA user_version=" + SCHEMA_VERSION);
                } else if (version != SCHEMA_VERSION) {
                    throw new FederationSecurityAuditUnavailable();
                }
                statement.executeQuery("""
                        SELECT event_id, timestamp_utc, event_type, source_service,
                               actor_type, actor_id, organization_id, action,
                               resource_type, resource_reference, outcome, reason_code,
                               correlation_id, metadata_json, contract_version
                        FROM federation_security_audit_events WHERE 1 = 0
                        """).close();
            }
        } catch (Exception ex) {
            if (ex instanceof FederationSecurityAuditUnavailable unavailable) {
                throw unavailable;
            }
            throw new FederationSecurityAuditUnavailable(ex);
        }
    }

    private Connection open() throws SQLException {
        Connection connection = DriverManager.getConnection(jdbcUrl);
        try {
            try (Statement statement = connection.createStatement()) {
                statement.execute("PRAGMA busy_timeout=5000");
            }
            return connection;
        } catch (SQLException | RuntimeException ex) {
            try {
                connection.close();
            } catch (SQLException closeFailure) {
                ex.addSuppressed(closeFailure);
            }
            throw ex;
        }
    }

    private static FederationSecurityAuditEvent requireEvent(FederationSecurityAuditEvent event) {
        if (event == null) {
            throw new IllegalArgumentException("Federation security audit event is required");
        }
        return new FederationSecurityAuditEvent(
                event.eventId(),
                event.timestampUtc(),
                event.eventType(),
                event.sourceService(),
                event.actorType(),
                event.actorId(),
                event.organizationId(),
                event.action(),
                event.resourceType(),
                event.resourceReference(),
                event.outcome(),
                event.reasonCode(),
                event.correlationId(),
                event.metadata(),
                event.contractVersion());
    }

    private static void rollback(Connection connection) {
        try {
            connection.rollback();
        } catch (SQLException ignored) {
            // The original persistence error remains authoritative.
        }
    }
}
