package lab.healthcare.minihis;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.annotation.Transactional;

import java.time.Clock;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

@Repository
public class MiniHisStore {

    private final JdbcTemplate jdbc;
    private final MiniHisSchema schema;
    private final Clock clock = Clock.systemUTC();

    public MiniHisStore(JdbcTemplate jdbc, MiniHisSchema schema) {
        this.jdbc = jdbc;
        this.schema = schema;
    }

    public void ensureReady() {
        schema.migrateExistingRows();
        if (count("patient") == 0 && count("consultation") == 0 && count("clinical_result") == 0) {
            insertSeed();
        } else {
            schema.backfillSyntheticAppointments();
        }
    }

    @Transactional
    public SeedCounts reset() {
        schema.migrateExistingRows();
        jdbc.update("DELETE FROM clinical_event");
        jdbc.update("DELETE FROM patient_identifier");
        jdbc.update("UPDATE appointment SET replaces_appointment_id = NULL");
        jdbc.update("DELETE FROM appointment");
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
        return attachIdentifiers(jdbc.query(
                """
                SELECT patient_id, family_name, given_name, birth_date, administrative_sex
                FROM patient
                ORDER BY patient_id ASC
                LIMIT ?
                """,
                (rs, row) -> patient(rs),
                limit));
    }

    public PatientLookup searchPatients(String system, String value, int limit) {
        int probe = limit + 1;
        List<PatientView> rows;
        if (SyntheticSeed.PROPRIETARY_PATIENT_SYSTEM.equals(system)) {
            rows = jdbc.query(
                    """
                    SELECT patient_id, family_name, given_name, birth_date, administrative_sex
                    FROM patient
                    WHERE patient_id = ?
                    LIMIT ?
                    """,
                    (rs, row) -> patient(rs),
                    value,
                    probe);
        } else {
            rows = jdbc.query(
                    """
                    SELECT p.patient_id, p.family_name, p.given_name, p.birth_date, p.administrative_sex
                    FROM patient p
                    INNER JOIN patient_identifier i ON i.patient_id = p.patient_id
                    WHERE i.identifier_system = ? AND i.identifier_value = ?
                    ORDER BY p.patient_id ASC
                    LIMIT ?
                    """,
                    (rs, row) -> patient(rs),
                    system,
                    value,
                    probe);
        }
        boolean truncated = rows.size() > limit;
        if (truncated) {
            rows = new ArrayList<>(rows.subList(0, limit));
        }
        return new PatientLookup(attachIdentifiers(rows), truncated);
    }

    public Optional<PatientView> findPatient(String patientId) {
        List<PatientView> rows = jdbc.query(
                """
                SELECT patient_id, family_name, given_name, birth_date, administrative_sex
                FROM patient
                WHERE patient_id = ?
                """,
                (rs, row) -> patient(rs),
                patientId);
        return attachIdentifiers(rows).stream().findFirst();
    }

    public Optional<List<ConsultationView>> listConsultations(String patientId, int limit) {
        if (findPatient(patientId).isEmpty()) {
            return Optional.empty();
        }
        return Optional.of(jdbc.query(
                """
                SELECT consultation_id, patient_id, occurred_at, reason, clinician_name, status, care_class, ended_at
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
                SELECT consultation_id, patient_id, occurred_at, reason, clinician_name, status, care_class, ended_at
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
                ORDER BY observed_at IS NULL, observed_at ASC, result_id ASC
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
                ORDER BY observed_at IS NULL, observed_at ASC, result_id ASC
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
                        ORDER BY observed_at IS NULL, observed_at ASC, result_id ASC
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
                        ORDER BY observed_at IS NULL, observed_at ASC, result_id ASC
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

    public AppointmentSearch searchAppointments(String patientId, int limit) {
        int probe = limit + 1;
        List<AppointmentView> rows = jdbc.query(
                """
                SELECT appointment_id, patient_id, status, start_offset_days, replaces_appointment_id
                FROM appointment
                WHERE patient_id = ?
                ORDER BY start_offset_days IS NULL, start_offset_days ASC, appointment_id ASC
                LIMIT ?
                """,
                (rs, row) -> appointment(rs),
                patientId,
                probe);
        boolean truncated = rows.size() > limit;
        if (truncated) {
            rows = List.copyOf(rows.subList(0, limit));
        }
        return new AppointmentSearch(rows, truncated);
    }

    public Optional<AppointmentView> findAppointment(String appointmentId) {
        List<AppointmentView> rows = jdbc.query(
                """
                SELECT appointment_id, patient_id, status, start_offset_days, replaces_appointment_id
                FROM appointment
                WHERE appointment_id = ?
                """,
                (rs, row) -> appointment(rs),
                appointmentId);
        return rows.stream().findFirst();
    }

    public Optional<List<EventView>> listEvents(String patientId, int limit) {
        if (findPatient(patientId).isEmpty()) {
            return Optional.empty();
        }
        return Optional.of(jdbc.query(
                """
                SELECT event_id, patient_id, resource_type, resource_id, change_type, occurred_at, detail
                FROM clinical_event
                WHERE patient_id = ?
                ORDER BY occurred_at IS NULL, occurred_at ASC, event_id ASC
                LIMIT ?
                """,
                (rs, row) -> new EventView(
                        rs.getString("event_id"),
                        rs.getString("patient_id"),
                        rs.getString("resource_type"),
                        rs.getString("resource_id"),
                        rs.getString("change_type"),
                        rs.getString("occurred_at"),
                        rs.getString("detail")),
                patientId,
                limit));
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
        for (SyntheticSeed.PatientIdentifierSeed identifier : SyntheticSeed.PATIENT_IDENTIFIERS) {
            jdbc.update(
                    """
                    INSERT INTO patient_identifier (identifier_system, identifier_value, patient_id)
                    VALUES (?, ?, ?)
                    """,
                    identifier.system(),
                    identifier.value(),
                    identifier.patientId());
        }
        for (SyntheticSeed.ConsultationSeed consultation : SyntheticSeed.CONSULTATIONS) {
            jdbc.update(
                    """
                    INSERT INTO consultation (
                        consultation_id, patient_id, occurred_at, reason, clinician_name, status, care_class, ended_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    consultation.consultationId(),
                    consultation.patientId(),
                    consultation.occurredAt(),
                    consultation.reason(),
                    consultation.clinicianName(),
                    consultation.status(),
                    consultation.careClass(),
                    consultation.endedAt());
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
        for (SyntheticSeed.AppointmentSeed appointment : SyntheticSeed.APPOINTMENTS) {
            jdbc.update(
                    """
                    INSERT INTO appointment (
                        appointment_id, patient_id, status, start_offset_days, replaces_appointment_id
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    appointment.appointmentId(),
                    appointment.patientId(),
                    appointment.status(),
                    appointment.startOffsetDays(),
                    appointment.replacesAppointmentId());
        }
        schema.recordSeedEvents();
    }

    private int count(String table) {
        Integer count = jdbc.queryForObject("SELECT COUNT(*) FROM " + table, Integer.class);
        return count == null ? 0 : count;
    }

    private static PatientView patient(java.sql.ResultSet rs) throws java.sql.SQLException {
        return new PatientView(
                rs.getString("patient_id"),
                rs.getString("family_name"),
                rs.getString("given_name"),
                rs.getString("birth_date"),
                rs.getString("administrative_sex"),
                List.of());
    }

    private List<PatientView> attachIdentifiers(List<PatientView> patients) {
        if (patients.isEmpty()) {
            return patients;
        }
        String placeholders = String.join(",", java.util.Collections.nCopies(patients.size(), "?"));
        Object[] ids = patients.stream().map(PatientView::patientId).toArray();
        Map<String, List<PatientIdentifierView>> grouped = new LinkedHashMap<>();
        jdbc.query(
                """
                SELECT patient_id, identifier_system, identifier_value
                FROM patient_identifier
                WHERE patient_id IN (%s)
                ORDER BY identifier_system ASC, identifier_value ASC
                """.formatted(placeholders),
                rs -> {
                    grouped.computeIfAbsent(rs.getString("patient_id"), key -> new ArrayList<>())
                            .add(new PatientIdentifierView(
                                    rs.getString("identifier_system"),
                                    rs.getString("identifier_value")));
                },
                ids);
        return patients.stream()
                .map(patient -> new PatientView(
                        patient.patientId(),
                        patient.familyName(),
                        patient.givenName(),
                        patient.birthDate(),
                        patient.administrativeSex(),
                        grouped.getOrDefault(patient.patientId(), List.of())))
                .toList();
    }

    private static ConsultationView consultation(java.sql.ResultSet rs) throws java.sql.SQLException {
        return new ConsultationView(
                rs.getString("consultation_id"),
                rs.getString("patient_id"),
                rs.getString("occurred_at"),
                rs.getString("reason"),
                rs.getString("clinician_name"),
                rs.getString("status"),
                rs.getString("care_class"),
                rs.getString("ended_at"));
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

    private AppointmentView appointment(java.sql.ResultSet rs) throws java.sql.SQLException {
        Object offset = rs.getObject("start_offset_days");
        String start = offset instanceof Number number
                ? AppointmentStart.atOffset(number.intValue(), clock)
                : null;
        return new AppointmentView(
                rs.getString("appointment_id"),
                rs.getString("patient_id"),
                rs.getString("status"),
                start,
                rs.getString("replaces_appointment_id"));
    }
}
