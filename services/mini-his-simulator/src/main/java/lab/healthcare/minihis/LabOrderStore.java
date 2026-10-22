package lab.healthcare.minihis;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Locale;
import java.util.Optional;
import java.util.UUID;

@Repository
public class LabOrderStore {

    private final JdbcTemplate jdbc;

    public LabOrderStore(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public LabOrderView insert(
            String patientId,
            String destinationSystemKey,
            String testCode,
            String testDescription,
            String requestedAt) {
        String orderId = "MHS-LAB-" + UUID.randomUUID().toString().replace("-", "").substring(0, 12).toUpperCase(Locale.ROOT);
        jdbc.update(
                """
                INSERT INTO lab_order (
                    order_id, patient_id, destination_system_key, test_code, test_description,
                    requested_at, local_status)
                VALUES (?, ?, ?, ?, ?, ?, 'recorded')
                """,
                orderId,
                patientId,
                destinationSystemKey,
                testCode,
                testDescription,
                requestedAt);
        return find(orderId).orElseThrow();
    }

    public Optional<LabOrderView> find(String orderId) {
        List<LabOrderView> rows = jdbc.query(
                """
                SELECT order_id, patient_id, destination_system_key, test_code, test_description,
                       requested_at, local_status, correlation_id, destination_order_id, destination_organization_id
                FROM lab_order
                WHERE order_id = ?
                """,
                (rs, row) -> new LabOrderView(
                        rs.getString("order_id"),
                        rs.getString("patient_id"),
                        rs.getString("destination_system_key"),
                        rs.getString("test_code"),
                        rs.getString("test_description"),
                        rs.getString("requested_at"),
                        rs.getString("local_status"),
                        rs.getString("correlation_id"),
                        rs.getString("destination_order_id"),
                        rs.getString("destination_organization_id")),
                orderId);
        return rows.stream().findFirst();
    }

    public void markSubmitted(String orderId, String correlationId, String destinationOrderId, String destinationOrganizationId) {
        jdbc.update(
                """
                UPDATE lab_order
                SET local_status = 'submitted', correlation_id = ?, destination_order_id = ?, destination_organization_id = ?
                WHERE order_id = ?
                """,
                correlationId,
                destinationOrderId,
                destinationOrganizationId,
                orderId);
    }

    public void markFailed(String orderId) {
        jdbc.update("UPDATE lab_order SET local_status = 'failed' WHERE order_id = ?", orderId);
    }
}
