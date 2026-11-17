package lab.healthcare.fhir.externalfhir;

import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;

/**
 * One row per external GET. The row stores the host, collection path, and status.
 * It does not store a logical id, the response body, a query string, or a credential.
 */
public final class ExternalFhirAudit {

    private final String jdbc;

    public ExternalFhirAudit(Path path) {
        try {
            Files.createDirectories(path.getParent());
        } catch (Exception ex) {
            throw new IllegalStateException("external fhir audit path");
        }
        this.jdbc = "jdbc:sqlite:" + path.toAbsolutePath();
        try (Connection connection = open()) {
            connection.createStatement().execute(
                    """
                    CREATE TABLE IF NOT EXISTS external_fhir_request (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        correlation_id TEXT NOT NULL,
                        method TEXT NOT NULL,
                        host TEXT NOT NULL,
                        path TEXT NOT NULL,
                        http_status INTEGER NOT NULL,
                        outcome TEXT NOT NULL,
                        resource_type TEXT NOT NULL,
                        resource_id TEXT NOT NULL
                    )
                    """);
        } catch (Exception ex) {
            throw new IllegalStateException("external fhir audit");
        }
    }

    public void record(
            String correlationId, String host, String path, int httpStatus, String outcome,
            String resourceType, String resourceId) {
        try (Connection connection = open();
                PreparedStatement statement = connection.prepareStatement(
                        """
                        INSERT INTO external_fhir_request
                        (correlation_id, method, host, path, http_status, outcome, resource_type, resource_id)
                        VALUES (?, 'GET', ?, ?, ?, ?, ?, ?)
                        """)) {
            statement.setString(1, correlationId);
            statement.setString(2, host);
            statement.setString(3, path);
            statement.setInt(4, httpStatus);
            statement.setString(5, outcome);
            statement.setString(6, resourceType);
            statement.setString(7, resourceId);
            statement.executeUpdate();
        } catch (Exception ex) {
            throw new IllegalStateException("external fhir audit");
        }
    }

    private Connection open() throws Exception {
        return DriverManager.getConnection(jdbc);
    }
}
