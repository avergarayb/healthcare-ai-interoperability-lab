package lab.healthcare.fhir.exchange;

import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.time.OffsetDateTime;
import java.util.Optional;

/**
 * Correlation database for the exchange. It is not the HAPI database, the Mini
 * HIS database, or the Mini LIS database.
 */
public final class SqliteExchangeStore implements ExchangeStore {

    private final String jdbcUrl;

    public SqliteExchangeStore(Path path) {
        if (path == null) {
            throw new IllegalArgumentException("Exchange store path is required");
        }
        try {
            Path parent = path.toAbsolutePath().getParent();
            if (parent != null) {
                Files.createDirectories(parent);
            }
        } catch (Exception ex) {
            throw new IllegalStateException("Exchange store directory cannot be created");
        }
        this.jdbcUrl = "jdbc:sqlite:" + path.toAbsolutePath();
        migrate();
    }

    @Override
    public synchronized Optional<String> findPatientLink(
            String sourceSystem, String identifierSystem, String identifierValue, String destinationSystem) {
        return queryString(
                """
                SELECT destination_patient_id FROM exchange_patient_link
                WHERE source_system = ? AND identifier_system = ? AND identifier_value = ? AND destination_system = ?
                """,
                sourceSystem,
                identifierSystem,
                identifierValue,
                destinationSystem);
    }

    @Override
    public synchronized void savePatientLink(
            String sourceSystem,
            String identifierSystem,
            String identifierValue,
            String destinationSystem,
            String destinationPatientId) {
        update(
                """
                INSERT INTO exchange_patient_link (
                    source_system, identifier_system, identifier_value, destination_system, destination_patient_id)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(source_system, identifier_system, identifier_value, destination_system) DO NOTHING
                """,
                sourceSystem,
                identifierSystem,
                identifierValue,
                destinationSystem,
                destinationPatientId);
    }

    @Override
    public synchronized Optional<OrderCorrelation> findOrder(
            String sourceSystem, String sourceOrganizationId, String sourceOrderId, String destinationSystem) {
        return queryOrder(
                """
                SELECT * FROM exchange_order
                WHERE source_system = ? AND source_organization_id = ? AND source_order_id = ? AND destination_system = ?
                """,
                sourceSystem,
                sourceOrganizationId,
                sourceOrderId,
                destinationSystem);
    }

    @Override
    public synchronized Optional<OrderCorrelation> findOwnedOrder(String sourceSystem, String sourceOrderId) {
        return queryOrder(
                "SELECT * FROM exchange_order WHERE source_system = ? AND source_order_id = ?",
                sourceSystem,
                sourceOrderId);
    }

    @Override
    public synchronized void insert(OrderCorrelation correlation) {
        update(
                """
                INSERT INTO exchange_order (
                    correlation_id, source_system, source_organization_id, source_order_id,
                    destination_system, destination_organization_id, destination_order_id, destination_patient_id,
                    patient_identifier_system, patient_identifier_value, test_code, test_description, requested_at,
                    delivery_state, error_code)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                correlation.correlationId(),
                correlation.sourceSystem(),
                correlation.sourceOrganizationId(),
                correlation.sourceOrderId(),
                correlation.destinationSystem(),
                correlation.destinationOrganizationId(),
                correlation.destinationOrderId(),
                correlation.destinationPatientId(),
                correlation.patientIdentifierSystem(),
                correlation.patientIdentifierValue(),
                correlation.testCode(),
                correlation.testDescription(),
                correlation.requestedAt().toString(),
                correlation.deliveryState(),
                correlation.errorCode());
    }

    @Override
    public synchronized void updateDelivery(
            String correlationId,
            String deliveryState,
            String errorCode,
            String destinationOrderId,
            String destinationPatientId) {
        update(
                """
                UPDATE exchange_order
                SET delivery_state = ?, error_code = ?, destination_order_id = COALESCE(?, destination_order_id),
                    destination_patient_id = COALESCE(?, destination_patient_id)
                WHERE correlation_id = ?
                """,
                deliveryState,
                errorCode,
                destinationOrderId,
                destinationPatientId,
                correlationId);
    }

    @Override
    public synchronized Optional<OrderCorrelation> findByDestinationOrder(String destinationSystem, String destinationOrderId) {
        return queryOrder(
                """
                SELECT * FROM exchange_order
                WHERE destination_system = ? AND destination_order_id = ?
                """,
                destinationSystem,
                destinationOrderId);
    }

    @Override
    public synchronized boolean saveHl7Observation(
            String messageControlId,
            String destinationOrderId,
            String sourceOrderId,
            String externalResultId,
            String observationJson) {
        try (Connection connection = open();
                PreparedStatement statement = connection.prepareStatement(
                        """
                        INSERT INTO exchange_hl7_result (
                            message_control_id, destination_order_id, source_order_id, external_result_id, observation_json)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(message_control_id) DO NOTHING
                        """)) {
            statement.setString(1, messageControlId);
            statement.setString(2, destinationOrderId);
            statement.setString(3, sourceOrderId);
            statement.setString(4, externalResultId);
            statement.setString(5, observationJson);
            return statement.executeUpdate() == 1;
        } catch (SQLException ex) {
            String state = ex.getSQLState();
            if ("23000".equals(state) || ex.getMessage() != null && ex.getMessage().contains("UNIQUE")) {
                return false;
            }
            throw ExchangeException.unavailable();
        }
    }

    @Override
    public synchronized java.util.List<String> hl7Observations(String destinationOrderId) {
        try (Connection connection = open();
                PreparedStatement statement = connection.prepareStatement(
                        """
                        SELECT observation_json FROM exchange_hl7_result
                        WHERE destination_order_id = ?
                        ORDER BY rowid
                        """)) {
            statement.setString(1, destinationOrderId);
            try (ResultSet rows = statement.executeQuery()) {
                java.util.ArrayList<String> found = new java.util.ArrayList<>();
                while (rows.next()) {
                    found.add(rows.getString(1));
                }
                return found;
            }
        } catch (SQLException ex) {
            throw ExchangeException.unavailable();
        }
    }

    private void migrate() {
        execute("""
                CREATE TABLE IF NOT EXISTS exchange_patient_link (
                    source_system TEXT NOT NULL,
                    identifier_system TEXT NOT NULL,
                    identifier_value TEXT NOT NULL,
                    destination_system TEXT NOT NULL,
                    destination_patient_id TEXT NOT NULL,
                    PRIMARY KEY (source_system, identifier_system, identifier_value, destination_system)
                )
                """);
        execute("""
                CREATE TABLE IF NOT EXISTS exchange_order (
                    correlation_id TEXT PRIMARY KEY,
                    source_system TEXT NOT NULL,
                    source_organization_id TEXT NOT NULL,
                    source_order_id TEXT NOT NULL,
                    destination_system TEXT NOT NULL,
                    destination_organization_id TEXT NOT NULL,
                    destination_order_id TEXT,
                    destination_patient_id TEXT,
                    patient_identifier_system TEXT NOT NULL,
                    patient_identifier_value TEXT NOT NULL,
                    test_code TEXT NOT NULL,
                    test_description TEXT NOT NULL,
                    requested_at TEXT NOT NULL,
                    delivery_state TEXT NOT NULL,
                    error_code TEXT,
                    UNIQUE (source_system, source_organization_id, source_order_id, destination_system)
                )
                """);
        execute("""
                CREATE TABLE IF NOT EXISTS exchange_hl7_result (
                    message_control_id TEXT PRIMARY KEY,
                    destination_order_id TEXT NOT NULL,
                    source_order_id TEXT NOT NULL,
                    external_result_id TEXT NOT NULL,
                    observation_json TEXT NOT NULL,
                    UNIQUE (destination_order_id, external_result_id)
                )
                """);
    }

    private void execute(String sql) {
        try (Connection connection = open(); PreparedStatement statement = connection.prepareStatement(sql)) {
            statement.execute();
        } catch (SQLException ex) {
            throw new IllegalStateException("Exchange store schema failed");
        }
    }

    private void update(String sql, Object... values) {
        try (Connection connection = open(); PreparedStatement statement = connection.prepareStatement(sql)) {
            bind(statement, values);
            statement.executeUpdate();
        } catch (SQLException ex) {
            throw ExchangeException.unavailable();
        }
    }

    private Optional<String> queryString(String sql, Object... values) {
        try (Connection connection = open(); PreparedStatement statement = connection.prepareStatement(sql)) {
            bind(statement, values);
            try (ResultSet rows = statement.executeQuery()) {
                if (!rows.next()) {
                    return Optional.empty();
                }
                return Optional.ofNullable(rows.getString(1));
            }
        } catch (SQLException ex) {
            throw ExchangeException.unavailable();
        }
    }

    private Optional<OrderCorrelation> queryOrder(String sql, Object... values) {
        try (Connection connection = open(); PreparedStatement statement = connection.prepareStatement(sql)) {
            bind(statement, values);
            try (ResultSet rows = statement.executeQuery()) {
                OrderCorrelation first = null;
                while (rows.next()) {
                    if (first != null) {
                        throw ExchangeException.invalidRequest();
                    }
                    first = map(rows);
                }
                return Optional.ofNullable(first);
            }
        } catch (SQLException ex) {
            throw ExchangeException.unavailable();
        }
    }

    private static OrderCorrelation map(ResultSet rows) throws SQLException {
        return new OrderCorrelation(
                rows.getString("correlation_id"),
                rows.getString("source_system"),
                rows.getString("source_organization_id"),
                rows.getString("source_order_id"),
                rows.getString("destination_system"),
                rows.getString("destination_organization_id"),
                rows.getString("destination_order_id"),
                rows.getString("destination_patient_id"),
                rows.getString("patient_identifier_system"),
                rows.getString("patient_identifier_value"),
                rows.getString("test_code"),
                rows.getString("test_description"),
                OffsetDateTime.parse(rows.getString("requested_at")),
                rows.getString("delivery_state"),
                rows.getString("error_code"));
    }

    private static void bind(PreparedStatement statement, Object... values) throws SQLException {
        for (int index = 0; index < values.length; index++) {
            statement.setObject(index + 1, values[index]);
        }
    }

    private Connection open() throws SQLException {
        Connection connection = DriverManager.getConnection(jdbcUrl);
        try (PreparedStatement pragma = connection.prepareStatement("PRAGMA busy_timeout = 5000")) {
            pragma.execute();
        }
        return connection;
    }
}
