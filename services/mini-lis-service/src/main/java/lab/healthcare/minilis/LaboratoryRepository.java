package lab.healthcare.minilis;

import org.springframework.dao.DataAccessException;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;

import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Timestamp;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.List;
import java.util.Optional;

@Repository
public class LaboratoryRepository {

    private static final RowMapper<ExternalPatient> PATIENT = (rs, row) -> new ExternalPatient(
            rs.getString("patient_id"),
            rs.getString("organization_id"),
            rs.getString("external_id"),
            rs.getString("family_name"),
            rs.getString("given_name"),
            rs.getObject("birth_date", LocalDate.class),
            rs.getString("administrative_sex"));

    private static final RowMapper<LabOrder> ORDER = (rs, row) -> new LabOrder(
            rs.getString("order_id"),
            rs.getString("patient_id"),
            rs.getString("requesting_organization_id"),
            rs.getString("external_request_id"),
            rs.getString("test_code"),
            rs.getString("test_description"),
            instant(rs, "requested_at"),
            OrderStatus.valueOf(rs.getString("status")));

    private static final RowMapper<LabResult> RESULT = (rs, row) -> new LabResult(
            rs.getString("result_id"),
            rs.getString("order_id"),
            rs.getString("patient_id"),
            rs.getString("external_result_id"),
            rs.getString("test_code"),
            rs.getString("result_value"),
            rs.getString("unit"),
            rs.getString("reference_range"),
            instant(rs, "resulted_at"),
            ResultStatus.valueOf(rs.getString("status")));

    private final JdbcTemplate jdbc;

    public LaboratoryRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public int countPatients() {
        Integer count = jdbc.queryForObject("SELECT COUNT(*) FROM external_patients", Integer.class);
        return count == null ? 0 : count;
    }

    public void insertPatient(ExternalPatient patient, OffsetDateTime createdAt) {
        write(() -> jdbc.update(
                """
                INSERT INTO external_patients (
                    patient_id, organization_id, external_id, family_name, given_name,
                    birth_date, administrative_sex, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                patient.patientId(),
                patient.organizationId(),
                patient.externalId(),
                patient.familyName(),
                patient.givenName(),
                patient.birthDate(),
                patient.administrativeSex(),
                Timestamp.from(createdAt.toInstant())));
    }

    public Optional<ExternalPatient> findPatient(String patientId) {
        return one(
                "SELECT * FROM external_patients WHERE patient_id = ?",
                PATIENT,
                patientId);
    }

    public List<ExternalPatient> searchPatients(String organizationId, String externalId) {
        return jdbc.query(
                """
                SELECT * FROM external_patients
                WHERE organization_id = ? AND external_id = ?
                ORDER BY patient_id
                """,
                PATIENT,
                organizationId,
                externalId);
    }

    public List<ExternalPatient> listPatients(int limit) {
        return jdbc.query(
                "SELECT * FROM external_patients ORDER BY patient_id LIMIT ?",
                PATIENT,
                limit);
    }

    public void insertOrder(LabOrder order, OffsetDateTime createdAt) {
        write(() -> jdbc.update(
                """
                INSERT INTO lab_orders (
                    order_id, patient_id, requesting_organization_id, external_request_id,
                    test_code, test_description, requested_at, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                order.orderId(),
                order.patientId(),
                order.requestingOrganizationId(),
                order.externalRequestId(),
                order.testCode(),
                order.testDescription(),
                Timestamp.from(order.requestedAt().toInstant()),
                order.status().name(),
                Timestamp.from(createdAt.toInstant())));
    }

    public Optional<LabOrder> findOrder(String orderId) {
        return one("SELECT * FROM lab_orders WHERE order_id = ?", ORDER, orderId);
    }

    public List<LabOrder> listOrders(int limit) {
        return jdbc.query("SELECT * FROM lab_orders ORDER BY requested_at, order_id LIMIT ?", ORDER, limit);
    }

    public List<LabOrder> listOrdersForPatient(String patientId) {
        return jdbc.query(
                "SELECT * FROM lab_orders WHERE patient_id = ? ORDER BY requested_at, order_id",
                ORDER,
                patientId);
    }

    public void updateOrderStatus(String orderId, OrderStatus status) {
        int updated = jdbc.update("UPDATE lab_orders SET status = ? WHERE order_id = ?", status.name(), orderId);
        if (updated != 1) {
            throw MiniLisException.notFound();
        }
    }

    public void insertResult(LabResult result, OffsetDateTime createdAt) {
        write(() -> jdbc.update(
                """
                INSERT INTO lab_results (
                    result_id, order_id, patient_id, external_result_id, test_code, result_value,
                    unit, reference_range, resulted_at, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                result.resultId(),
                result.orderId(),
                result.patientId(),
                result.externalResultId(),
                result.testCode(),
                result.value(),
                result.unit(),
                result.referenceRange(),
                Timestamp.from(result.resultedAt().toInstant()),
                result.status().name(),
                Timestamp.from(createdAt.toInstant())));
    }

    public Optional<LabResult> findResult(String resultId) {
        return one("SELECT * FROM lab_results WHERE result_id = ?", RESULT, resultId);
    }

    public List<LabResult> listResultsForOrder(String orderId) {
        return jdbc.query(
                "SELECT * FROM lab_results WHERE order_id = ? ORDER BY resulted_at, result_id",
                RESULT,
                orderId);
    }

    public List<LabResult> listResultsForPatient(String patientId) {
        return jdbc.query(
                """
                SELECT r.* FROM lab_results r
                JOIN lab_orders o ON o.order_id = r.order_id
                WHERE o.patient_id = ?
                ORDER BY r.resulted_at, r.result_id
                """,
                RESULT,
                patientId);
    }

    public boolean hasFinalResult(String orderId) {
        Integer count = jdbc.queryForObject(
                "SELECT COUNT(*) FROM lab_results WHERE order_id = ? AND status = 'FINAL'",
                Integer.class,
                orderId);
        return count != null && count > 0;
    }

    private <T> Optional<T> one(String sql, RowMapper<T> mapper, String id) {
        List<T> rows = jdbc.query(sql, mapper, id);
        if (rows.isEmpty()) {
            return Optional.empty();
        }
        if (rows.size() != 1) {
            throw MiniLisException.unavailable();
        }
        return Optional.of(rows.get(0));
    }

    private static void write(Runnable insert) {
        try {
            insert.run();
        } catch (DuplicateKeyException ex) {
            throw MiniLisException.duplicate();
        } catch (DataAccessException ex) {
            throw MiniLisException.unavailable();
        }
    }

    private static OffsetDateTime instant(ResultSet rs, String column) throws SQLException {
        Timestamp timestamp = rs.getTimestamp(column);
        if (timestamp == null) {
            throw MiniLisException.unavailable();
        }
        return timestamp.toInstant().atOffset(ZoneOffset.UTC);
    }
}
