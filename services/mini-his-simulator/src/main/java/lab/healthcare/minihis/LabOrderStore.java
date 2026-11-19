package lab.healthcare.minihis;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Locale;
import java.util.Map;
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

    public List<LabOrderView> listByPatient(String patientId) {
        return jdbc.query(
                """
                SELECT order_id, patient_id, destination_system_key, test_code, test_description,
                       requested_at, local_status, correlation_id, destination_order_id, destination_organization_id
                FROM lab_order
                WHERE patient_id = ?
                ORDER BY order_id
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
                patientId);
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

    public List<LabOrderView> listAll() {
        return jdbc.query(
                """
                SELECT order_id, patient_id, destination_system_key, test_code, test_description,
                       requested_at, local_status, correlation_id, destination_order_id, destination_organization_id
                FROM lab_order
                ORDER BY requested_at DESC
                """,
                (rs, row) -> map(rs));
    }

    public void rememberContext(String orderId, String episodeId, String indication) {
        jdbc.update("DELETE FROM lab_order_context WHERE order_id = ?", orderId);
        jdbc.update(
                "INSERT INTO lab_order_context (order_id, episode_id, indication) VALUES (?, ?, ?)",
                orderId,
                blank(episodeId),
                blank(indication));
    }

    public Map<String, Object> context(String orderId) {
        List<Map<String, Object>> rows = jdbc.queryForList("SELECT * FROM lab_order_context WHERE order_id = ?", orderId);
        return rows.isEmpty() ? Map.of() : rows.get(0);
    }

    public void rememberProposal(String orderId, String proposalId, String proposalHash, String summary, String phase, String protocols) {
        jdbc.update(
                """
                UPDATE lab_order_context
                SET proposal_id = ?, proposal_hash = ?, proposal_summary = ?, proposal_phase = ?, protocol_ids = ?
                WHERE order_id = ?
                """,
                proposalId, proposalHash, summary, phase, protocols, orderId);
    }

    public void insertAcknowledgement(String orderId, String proposalId, String proposalHash, String title, String actorId, String createdAt) {
        jdbc.update(
                """
                INSERT INTO lab_acknowledgement (
                    order_id, proposal_id, proposal_hash, title, status, actor_id, created_at)
                VALUES (?, ?, ?, ?, 'open', ?, ?)
                """,
                orderId, proposalId, proposalHash, title, actorId, createdAt);
    }

    public Optional<Map<String, Object>> acknowledgement(String orderId) {
        List<Map<String, Object>> rows = jdbc.queryForList("SELECT * FROM lab_acknowledgement WHERE order_id = ?", orderId);
        return rows.stream().findFirst();
    }

    public void markAcknowledged(String orderId, String at) {
        jdbc.update(
                "UPDATE lab_acknowledgement SET status = 'acknowledged', acknowledged_at = ? WHERE order_id = ? AND status = 'open'",
                at, orderId);
    }

    public void markEscalated(String orderId, String at) {
        jdbc.update(
                "UPDATE lab_acknowledgement SET status = 'escalated', acknowledged_at = ? WHERE order_id = ? AND status = 'open'",
                at, orderId);
    }

    private static LabOrderView map(java.sql.ResultSet rs) throws java.sql.SQLException {
        return new LabOrderView(
                rs.getString("order_id"),
                rs.getString("patient_id"),
                rs.getString("destination_system_key"),
                rs.getString("test_code"),
                rs.getString("test_description"),
                rs.getString("requested_at"),
                rs.getString("local_status"),
                rs.getString("correlation_id"),
                rs.getString("destination_order_id"),
                rs.getString("destination_organization_id"));
    }

    private static String blank(String value) {
        return value == null || value.isBlank() ? null : value.trim();
    }
}
