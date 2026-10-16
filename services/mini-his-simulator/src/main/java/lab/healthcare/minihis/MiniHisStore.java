package lab.healthcare.minihis;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

@Repository
public class MiniHisStore {

    private final JdbcTemplate jdbc;
    private final MiniHisSchema schema;

    public MiniHisStore(JdbcTemplate jdbc, MiniHisSchema schema) {
        this.jdbc = jdbc;
        this.schema = schema;
    }

    public void ensureReady() {
        schema.createIfAbsent();
        if (count("patient") == 0 && count("consultation") == 0 && count("clinical_result") == 0) {
            insertSeed();
        }
    }

    @Transactional
    public SeedCounts reset() {
        schema.createIfAbsent();
        jdbc.update("DELETE FROM clinical_result_component");
        jdbc.update("DELETE FROM clinical_result");
        jdbc.update("DELETE FROM consultation");
        jdbc.update("DELETE FROM patient");
        insertSeed();
        return counts();
    }

    public SeedCounts counts() {
        return new SeedCounts(count("patient"), count("consultation"), count("clinical_result"));
    }

    public List<PatientView> listPatients(int limit) {
        return jdbc.query(
                """
                SELECT patient_id, family_name, given_name, birth_date, administrative_sex
                FROM patient
                ORDER BY patient_id ASC
                LIMIT ?
                """,
                (rs, row) -> new PatientView(
                        rs.getString("patient_id"),
                        rs.getString("family_name"),
                        rs.getString("given_name"),
                        rs.getString("birth_date"),
                        rs.getString("administrative_sex")),
                limit);
    }

    public Optional<PatientView> findPatient(String patientId) {
        List<PatientView> rows = jdbc.query(
                """
                SELECT patient_id, family_name, given_name, birth_date, administrative_sex
                FROM patient
                WHERE patient_id = ?
                """,
                (rs, row) -> new PatientView(
                        rs.getString("patient_id"),
                        rs.getString("family_name"),
                        rs.getString("given_name"),
                        rs.getString("birth_date"),
                        rs.getString("administrative_sex")),
                patientId);
        return rows.stream().findFirst();
    }

    public Optional<List<ConsultationView>> listConsultations(String patientId, int limit) {
        if (findPatient(patientId).isEmpty()) {
            return Optional.empty();
        }
        return Optional.of(jdbc.query(
                """
                SELECT consultation_id, patient_id, occurred_at, reason, clinician_name, status, care_class
                FROM consultation
                WHERE patient_id = ?
                ORDER BY occurred_at DESC, consultation_id ASC
                LIMIT ?
                """,
                (rs, row) -> consultation(rs),
                patientId,
                limit));
    }

    public Optional<ConsultationView> findConsultation(String consultationId) {
        List<ConsultationView> rows = jdbc.query(
                """
                SELECT consultation_id, patient_id, occurred_at, reason, clinician_name, status, care_class
                FROM consultation
                WHERE consultation_id = ?
                """,
                (rs, row) -> consultation(rs),
                consultationId);
        return rows.stream().findFirst();
    }

    public Optional<List<ResultView>> listResultsForConsultation(String consultationId, int limit) {
        if (findConsultation(consultationId).isEmpty()) {
            return Optional.empty();
        }
        return Optional.of(attachComponents(jdbc.query(
                """
                SELECT result_id, consultation_id, patient_id, result_type, display_name,
                       value_text, unit, observed_at, status
                FROM clinical_result
                WHERE consultation_id = ?
                ORDER BY observed_at ASC, result_id ASC
                LIMIT ?
                """,
                (rs, row) -> result(rs),
                consultationId,
                limit)));
    }

    public Optional<List<ResultView>> listResultsForPatient(String patientId, int limit) {
        if (findPatient(patientId).isEmpty()) {
            return Optional.empty();
        }
        return Optional.of(attachComponents(jdbc.query(
                """
                SELECT result_id, consultation_id, patient_id, result_type, display_name,
                       value_text, unit, observed_at, status
                FROM clinical_result
                WHERE patient_id = ?
                ORDER BY observed_at ASC, result_id ASC
                LIMIT ?
                """,
                (rs, row) -> result(rs),
                patientId,
                limit)));
    }

    public ResultSearch searchResults(String patientId, String status, int limit) {
        int probe = limit + 1;
        List<ResultView> rows = status == null
                ? jdbc.query(
                        """
                        SELECT result_id, consultation_id, patient_id, result_type, display_name,
                               value_text, unit, observed_at, status
                        FROM clinical_result
                        WHERE patient_id = ?
                        ORDER BY observed_at ASC, result_id ASC
                        LIMIT ?
                        """,
                        (rs, row) -> result(rs),
                        patientId,
                        probe)
                : jdbc.query(
                        """
                        SELECT result_id, consultation_id, patient_id, result_type, display_name,
                               value_text, unit, observed_at, status
                        FROM clinical_result
                        WHERE patient_id = ? AND status = ?
                        ORDER BY observed_at ASC, result_id ASC
                        LIMIT ?
                        """,
                        (rs, row) -> result(rs),
                        patientId,
                        status,
                        probe);
        boolean truncated = rows.size() > limit;
        if (truncated) {
            rows = List.copyOf(rows.subList(0, limit));
        }
        return new ResultSearch(attachComponents(rows), truncated);
    }

    public Optional<ResultView> findResult(String resultId) {
        List<ResultView> rows = jdbc.query(
                """
                SELECT result_id, consultation_id, patient_id, result_type, display_name,
                       value_text, unit, observed_at, status
                FROM clinical_result
                WHERE result_id = ?
                """,
                (rs, row) -> result(rs),
                resultId);
        return attachComponents(rows).stream().findFirst();
    }

    public boolean foreignKeysEnabled() {
        Integer enabled = jdbc.queryForObject("PRAGMA foreign_keys", Integer.class);
        return enabled != null && enabled == 1;
    }

    private void insertSeed() {
        for (SyntheticSeed.PatientSeed patient : SyntheticSeed.PATIENTS) {
            jdbc.update(
                    """
                    INSERT INTO patient (patient_id, family_name, given_name, birth_date, administrative_sex)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    patient.patientId(),
                    patient.familyName(),
                    patient.givenName(),
                    patient.birthDate(),
                    patient.administrativeSex());
        }
        for (SyntheticSeed.ConsultationSeed consultation : SyntheticSeed.CONSULTATIONS) {
            jdbc.update(
                    """
                    INSERT INTO consultation (
                        consultation_id, patient_id, occurred_at, reason, clinician_name, status, care_class
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    consultation.consultationId(),
                    consultation.patientId(),
                    consultation.occurredAt(),
                    consultation.reason(),
                    consultation.clinicianName(),
                    consultation.status(),
                    consultation.careClass());
        }
        for (SyntheticSeed.ResultSeed result : SyntheticSeed.RESULTS) {
            jdbc.update(
                    """
                    INSERT INTO clinical_result (
                        result_id, consultation_id, patient_id, result_type, display_name,
                        value_text, unit, observed_at, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    result.resultId(),
                    result.consultationId(),
                    result.patientId(),
                    result.resultType(),
                    result.displayName(),
                    result.valueText(),
                    result.unit(),
                    result.observedAt(),
                    result.status());
        }
        for (SyntheticSeed.ComponentSeed component : SyntheticSeed.COMPONENTS) {
            jdbc.update(
                    """
                    INSERT INTO clinical_result_component (
                        component_id, result_id, component_name, value_decimal, unit
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    component.componentId(),
                    component.resultId(),
                    component.name(),
                    component.valueDecimal(),
                    component.unit());
        }
    }

    private int count(String table) {
        Integer count = jdbc.queryForObject("SELECT COUNT(*) FROM " + table, Integer.class);
        return count == null ? 0 : count;
    }

    private static ConsultationView consultation(java.sql.ResultSet rs) throws java.sql.SQLException {
        return new ConsultationView(
                rs.getString("consultation_id"),
                rs.getString("patient_id"),
                rs.getString("occurred_at"),
                rs.getString("reason"),
                rs.getString("clinician_name"),
                rs.getString("status"),
                rs.getString("care_class"));
    }

    private static ResultView result(java.sql.ResultSet rs) throws java.sql.SQLException {
        return new ResultView(
                rs.getString("result_id"),
                rs.getString("consultation_id"),
                rs.getString("patient_id"),
                rs.getString("result_type"),
                rs.getString("display_name"),
                rs.getString("value_text"),
                rs.getString("unit"),
                rs.getString("observed_at"),
                rs.getString("status"),
                List.of());
    }

    private List<ResultView> attachComponents(List<ResultView> rows) {
        if (rows.isEmpty()) {
            return rows;
        }
        String placeholders = String.join(", ", java.util.Collections.nCopies(rows.size(), "?"));
        Object[] ids = rows.stream().map(ResultView::resultId).toArray();
        Map<String, List<ResultComponentView>> grouped = new LinkedHashMap<>();
        jdbc.query(
                """
                SELECT component_id, result_id, component_name, value_decimal, unit
                FROM clinical_result_component
                WHERE result_id IN (%s)
                ORDER BY component_id ASC
                """.formatted(placeholders),
                rs -> {
                    String resultId = rs.getString("result_id");
                    grouped.computeIfAbsent(resultId, key -> new ArrayList<>())
                            .add(new ResultComponentView(
                                    rs.getString("component_id"),
                                    rs.getString("component_name"),
                                    rs.getString("value_decimal"),
                                    rs.getString("unit")));
                },
                ids);
        return rows.stream()
                .map(row -> new ResultView(
                        row.resultId(),
                        row.consultationId(),
                        row.patientId(),
                        row.resultType(),
                        row.displayName(),
                        row.valueText(),
                        row.unit(),
                        row.observedAt(),
                        row.status(),
                        List.copyOf(grouped.getOrDefault(row.resultId(), List.of()))))
                .toList();
    }
}
