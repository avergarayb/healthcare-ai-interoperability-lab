package lab.healthcare.fhir.externalfhir;

import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.util.Optional;

/**
 * Explicit local-to-external patient link. A matching identifier or name
 * does not create a row. This store is not the Mini HIS or Mini LIS database.
 */
public final class ExternalPatientLinkStore {

    private final String jdbc;
    private final String destinationSystem;

    public ExternalPatientLinkStore(Path path, String destinationSystem) {
        try {
            Files.createDirectories(path.getParent());
        } catch (Exception ex) {
            throw new IllegalStateException("external patient link path");
        }
        this.jdbc = "jdbc:sqlite:" + path.toAbsolutePath();
        this.destinationSystem = destinationSystem;
        try (Connection connection = open()) {
            connection.createStatement().execute(
                    """
                    CREATE TABLE IF NOT EXISTS external_patient_link (
                        caller_system TEXT NOT NULL,
                        identifier_system TEXT NOT NULL,
                        identifier_value TEXT NOT NULL,
                        destination_system TEXT NOT NULL,
                        destination_patient_id TEXT NOT NULL,
                        PRIMARY KEY (
                            caller_system, identifier_system, identifier_value, destination_system)
                    )
                    """);
        } catch (Exception ex) {
            throw new IllegalStateException("external patient link");
        }
    }

    public boolean owns(String sourceKey) {
        return destinationSystem.equals(sourceKey);
    }

    public void assign(
            String callerSystem, String identifierSystem, String identifierValue, String destinationPatientId) {
        Optional<String> current = find(callerSystem, identifierSystem, identifierValue, destinationSystem);
        if (current.isPresent()) {
            if (!current.get().equals(destinationPatientId)) {
                throw new IllegalStateException("external patient link conflict");
            }
            return;
        }
        try (Connection connection = open();
                PreparedStatement statement = connection.prepareStatement(
                        """
                        INSERT INTO external_patient_link
                        (caller_system, identifier_system, identifier_value, destination_system, destination_patient_id)
                        VALUES (?, ?, ?, ?, ?)
                        """)) {
            statement.setString(1, callerSystem);
            statement.setString(2, identifierSystem);
            statement.setString(3, identifierValue);
            statement.setString(4, destinationSystem);
            statement.setString(5, destinationPatientId);
            statement.executeUpdate();
        } catch (Exception ex) {
            throw new IllegalStateException("external patient link");
        }
    }

    public Optional<String> find(
            String callerSystem, String identifierSystem, String identifierValue, String destination) {
        if (!destinationSystem.equals(destination)) {
            return Optional.empty();
        }
        try (Connection connection = open();
                PreparedStatement statement = connection.prepareStatement(
                        """
                        SELECT destination_patient_id FROM external_patient_link
                        WHERE caller_system=? AND identifier_system=? AND identifier_value=?
                          AND destination_system=?
                        """)) {
            statement.setString(1, callerSystem);
            statement.setString(2, identifierSystem);
            statement.setString(3, identifierValue);
            statement.setString(4, destination);
            try (ResultSet rows = statement.executeQuery()) {
                if (!rows.next()) {
                    return Optional.empty();
                }
                return Optional.of(rows.getString(1));
            }
        } catch (Exception ex) {
            throw new IllegalStateException("external patient link");
        }
    }

    private Connection open() throws Exception {
        return DriverManager.getConnection(jdbc);
    }
}
