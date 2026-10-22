package lab.healthcare.minihis;

import org.springframework.jdbc.core.ConnectionCallback;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

import java.sql.Connection;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

@Component
public class MiniHisSchema {

    private final JdbcTemplate jdbc;

    public MiniHisSchema(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public void migrateExistingRows() {
        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS patient (
                    patient_id TEXT PRIMARY KEY,
                    family_name TEXT NOT NULL,
                    given_name TEXT NOT NULL,
                    birth_date TEXT NOT NULL,
                    administrative_sex TEXT NOT NULL
                        CHECK (administrative_sex IN ('female', 'male', 'unknown'))
                )
                """);
        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS consultation (
                    consultation_id TEXT PRIMARY KEY,
                    patient_id TEXT NOT NULL REFERENCES patient(patient_id),
                    occurred_at TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    clinician_name TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (status IN ('completed', 'in_progress', 'scheduled', 'cancelled')),
                    care_class TEXT,
                    ended_at TEXT
                )
                """);
        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS clinical_result (
                    result_id TEXT PRIMARY KEY,
                    consultation_id TEXT NOT NULL REFERENCES consultation(consultation_id),
                    patient_id TEXT NOT NULL REFERENCES patient(patient_id),
                    result_type TEXT NOT NULL CHECK (result_type IN ('laboratory', 'vital_sign')),
                    display_name TEXT NOT NULL,
                    value_text TEXT NOT NULL,
                    unit TEXT NOT NULL,
                    observed_at TEXT,
                    status TEXT
                )
                """);
        jdbc.execute("""
                CREATE TRIGGER IF NOT EXISTS clinical_result_same_patient_insert
                BEFORE INSERT ON clinical_result
                FOR EACH ROW
                WHEN NEW.patient_id <> (
                    SELECT patient_id FROM consultation WHERE consultation_id = NEW.consultation_id
                )
                BEGIN
                    SELECT RAISE(ABORT, 'result patient does not match consultation');
                END
                """);
        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS clinical_result_component (
                    component_id TEXT PRIMARY KEY,
                    result_id TEXT NOT NULL REFERENCES clinical_result(result_id),
                    component_name TEXT NOT NULL,
                    value_decimal TEXT NOT NULL,
                    unit TEXT NOT NULL
                )
                """);
        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS appointment (
                    appointment_id TEXT PRIMARY KEY,
                    patient_id TEXT NOT NULL REFERENCES patient(patient_id),
                    status TEXT NOT NULL CHECK (status IN (
                        'not_attended', 'confirmed', 'scheduled', 'completed', 'cancelled')),
                    start_offset_days INTEGER,
                    replaces_appointment_id TEXT
                )
                """);
        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS patient_identifier (
                    identifier_system TEXT NOT NULL,
                    identifier_value TEXT NOT NULL,
                    patient_id TEXT NOT NULL REFERENCES patient(patient_id),
                    PRIMARY KEY (identifier_system, identifier_value)
                )
                """);
        addColumnIfAbsent("consultation", "care_class", "TEXT");
        addColumnIfAbsent("clinical_result", "status", "TEXT");
        backfillSyntheticCareClass();
        backfillSyntheticResultStatus();
        backfillSyntheticBloodPressure();
        widenLongitudinalModel();
    }

    public void createIfAbsent() {
        migrateExistingRows();
        backfillSyntheticAppointments();
    }

    public void backfillSyntheticAppointments() {
        for (SyntheticSeed.PatientSeed patient : SyntheticSeed.PATIENTS) {
            if (patient.patientId().compareTo("MHS-PAT-004") < 0) {
                continue;
            }
            jdbc.update(
                    """
                    INSERT INTO patient (
                        patient_id, family_name, given_name, birth_date, administrative_sex
                    )
                    SELECT ?, ?, ?, ?, ?
                    WHERE NOT EXISTS (SELECT 1 FROM patient WHERE patient_id = ?)
                    """,
                    patient.patientId(),
                    patient.familyName(),
                    patient.givenName(),
                    patient.birthDate(),
                    patient.administrativeSex(),
                    patient.patientId());
        }
        for (SyntheticSeed.AppointmentSeed appointment : SyntheticSeed.APPOINTMENTS) {
            jdbc.update(
                    """
                    INSERT INTO appointment (
                        appointment_id, patient_id, status, start_offset_days, replaces_appointment_id
                    )
                    SELECT ?, ?, ?, ?, ?
                    WHERE EXISTS (SELECT 1 FROM patient WHERE patient_id = ?)
                      AND NOT EXISTS (SELECT 1 FROM appointment WHERE appointment_id = ?)
                    """,
                    appointment.appointmentId(),
                    appointment.patientId(),
                    appointment.status(),
                    appointment.startOffsetDays(),
                    appointment.replacesAppointmentId(),
                    appointment.patientId(),
                    appointment.appointmentId());
        }
        for (SyntheticSeed.ConsultationSeed consultation : SyntheticSeed.CONSULTATIONS) {
            if (!SyntheticSeed.backfilledConsultation(consultation.consultationId())) {
                continue;
            }
            jdbc.update(
                    """
                    INSERT INTO consultation (
                        consultation_id, patient_id, occurred_at, reason, clinician_name,
                        status, care_class, ended_at
                    )
                    SELECT ?, ?, ?, ?, ?, ?, ?, ?
                    WHERE EXISTS (SELECT 1 FROM patient WHERE patient_id = ?)
                      AND NOT EXISTS (SELECT 1 FROM consultation WHERE consultation_id = ?)
                    """,
                    consultation.consultationId(),
                    consultation.patientId(),
                    consultation.occurredAt(),
                    consultation.reason(),
                    consultation.clinicianName(),
                    consultation.status(),
                    consultation.careClass(),
                    consultation.endedAt(),
                    consultation.patientId(),
                    consultation.consultationId());
        }
        for (SyntheticSeed.ResultSeed result : SyntheticSeed.RESULTS) {
            if (!SyntheticSeed.backfilledResult(result.resultId())) {
                continue;
            }
            jdbc.update(
                    """
                    INSERT INTO clinical_result (
                        result_id, consultation_id, patient_id, result_type, display_name,
                        value_text, unit, observed_at, status
                    )
                    SELECT ?, ?, ?, ?, ?, ?, ?, ?, ?
                    WHERE EXISTS (SELECT 1 FROM consultation WHERE consultation_id = ?)
                      AND NOT EXISTS (SELECT 1 FROM clinical_result WHERE result_id = ?)
                    """,
                    result.resultId(),
                    result.consultationId(),
                    result.patientId(),
                    result.resultType(),
                    result.displayName(),
                    result.valueText(),
                    result.unit(),
                    result.observedAt(),
                    result.status(),
                    result.consultationId(),
                    result.resultId());
        }
        for (SyntheticSeed.PatientIdentifierSeed identifier : SyntheticSeed.PATIENT_IDENTIFIERS) {
            jdbc.update(
                    """
                    INSERT INTO patient_identifier (identifier_system, identifier_value, patient_id)
                    SELECT ?, ?, ?
                    WHERE EXISTS (SELECT 1 FROM patient WHERE patient_id = ?)
                      AND NOT EXISTS (
                          SELECT 1 FROM patient_identifier
                          WHERE identifier_system = ? AND identifier_value = ?
                      )
                    """,
                    identifier.system(),
                    identifier.value(),
                    identifier.patientId(),
                    identifier.patientId(),
                    identifier.system(),
                    identifier.value());
        }
        recordSeedEvents();
    }

    public void recordSeedEvents() {
        for (SyntheticSeed.ConsultationSeed consultation : SyntheticSeed.CONSULTATIONS) {
            recordEvent(
                    "EVT-" + consultation.consultationId(),
                    consultation.patientId(),
                    "consultation",
                    consultation.consultationId(),
                    "recorded",
                    consultation.occurredAt(),
                    "consultation_recorded");
        }
        for (SyntheticSeed.ResultSeed result : SyntheticSeed.RESULTS) {
            recordEvent(
                    "EVT-" + result.resultId(),
                    result.patientId(),
                    "result",
                    result.resultId(),
                    "recorded",
                    result.observedAt(),
                    "result_recorded");
        }
        for (SyntheticSeed.AppointmentSeed appointment : SyntheticSeed.APPOINTMENTS) {
            String offset = appointment.startOffsetDays() == null
                    ? "missing"
                    : Integer.toString(appointment.startOffsetDays());
            recordEvent(
                    "EVT-" + appointment.appointmentId(),
                    appointment.patientId(),
                    "appointment",
                    appointment.appointmentId(),
                    "recorded",
                    null,
                    "appointment_recorded;start_offset:" + offset);
            if (appointment.replacesAppointmentId() != null) {
                recordEvent(
                        "EVT-" + appointment.appointmentId() + "-replaces",
                        appointment.patientId(),
                        "appointment",
                        appointment.appointmentId(),
                        "replaces",
                        null,
                        "replaces:" + appointment.replacesAppointmentId());
            }
        }
    }

    private void recordEvent(
            String eventId,
            String patientId,
            String recordKind,
            String resourceId,
            String changeType,
            String occurredAt,
            String detail) {
        jdbc.update(
                """
                INSERT INTO clinical_event (
                    event_id, patient_id, resource_type, resource_id, change_type, occurred_at, detail
                )
                SELECT ?, ?, ?, ?, ?, ?, ?
                WHERE EXISTS (SELECT 1 FROM patient WHERE patient_id = ?)
                  AND NOT EXISTS (SELECT 1 FROM clinical_event WHERE event_id = ?)
                """,
                eventId,
                patientId,
                recordKind,
                resourceId,
                changeType,
                occurredAt,
                detail,
                patientId,
                eventId);
    }

    private void widenLongitudinalModel() {
        jdbc.execute("CREATE TABLE IF NOT EXISTS schema_marker (name TEXT PRIMARY KEY)");
        Integer present = jdbc.queryForObject(
                "SELECT COUNT(*) FROM schema_marker WHERE name = 'longitudinal-v2'", Integer.class);
        if (present != null && present > 0) {
            createEventTable();
            return;
        }
        boolean copyReplaces = columnNames("appointment").contains("replaces_appointment_id");
        jdbc.execute((ConnectionCallback<Void>) connection -> {
            rebuildLongitudinalTables(connection, copyReplaces);
            return null;
        });
    }

    private void rebuildLongitudinalTables(Connection connection, boolean copyReplaces) throws SQLException {
        boolean originalAutoCommit = connection.getAutoCommit();
        try (Statement statement = connection.createStatement()) {
            statement.execute("PRAGMA foreign_keys=OFF");
            connection.setAutoCommit(false);
            try {
                execute(statement, "DROP TRIGGER IF EXISTS clinical_result_same_patient_insert");
                execute(statement, "DROP TABLE IF EXISTS consultation_next");
                execute(statement, "DROP TABLE IF EXISTS clinical_result_next");
                execute(statement, "DROP TABLE IF EXISTS appointment_next");
                execute(statement, """
                CREATE TABLE consultation_next (
                    consultation_id TEXT PRIMARY KEY,
                    patient_id TEXT NOT NULL REFERENCES patient(patient_id),
                    occurred_at TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    clinician_name TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (status IN ('completed', 'in_progress', 'scheduled', 'cancelled')),
                    care_class TEXT,
                    ended_at TEXT
                )
                """);
                execute(statement, """
                INSERT INTO consultation_next (
                    consultation_id, patient_id, occurred_at, reason, clinician_name, status, care_class, ended_at
                )
                SELECT consultation_id, patient_id, occurred_at, reason, clinician_name, status, care_class,
                       CASE WHEN status = 'completed' THEN occurred_at ELSE NULL END
                        FROM consultation
                """);
                execute(statement, "DROP TABLE consultation");
                execute(statement, "ALTER TABLE consultation_next RENAME TO consultation");
                execute(statement, """
                CREATE TABLE clinical_result_next (
                    result_id TEXT PRIMARY KEY,
                    consultation_id TEXT NOT NULL REFERENCES consultation(consultation_id),
                    patient_id TEXT NOT NULL REFERENCES patient(patient_id),
                    result_type TEXT NOT NULL CHECK (result_type IN ('laboratory', 'vital_sign')),
                    display_name TEXT NOT NULL,
                    value_text TEXT NOT NULL,
                    unit TEXT NOT NULL,
                    observed_at TEXT,
                    status TEXT
                )
                """);
                execute(statement, """
                INSERT INTO clinical_result_next (
                    result_id, consultation_id, patient_id, result_type, display_name,
                    value_text, unit, observed_at, status
                )
                SELECT result_id, consultation_id, patient_id, result_type, display_name,
                       value_text, unit, observed_at, status
                        FROM clinical_result
                """);
                execute(statement, "DROP TABLE clinical_result");
                execute(statement, "ALTER TABLE clinical_result_next RENAME TO clinical_result");
                execute(statement, """
                CREATE TABLE appointment_next (
                    appointment_id TEXT PRIMARY KEY,
                    patient_id TEXT NOT NULL REFERENCES patient(patient_id),
                    status TEXT NOT NULL CHECK (status IN (
                        'not_attended', 'confirmed', 'scheduled', 'completed', 'cancelled')),
                    start_offset_days INTEGER,
                    replaces_appointment_id TEXT
                )
                """);
                if (copyReplaces) {
                    execute(statement, """
                            INSERT INTO appointment_next (
                                appointment_id, patient_id, status, start_offset_days, replaces_appointment_id
                            )
                            SELECT appointment_id, patient_id, status, start_offset_days, replaces_appointment_id
                            FROM appointment
                            """);
                } else {
                    execute(statement, """
                            INSERT INTO appointment_next (
                                appointment_id, patient_id, status, start_offset_days, replaces_appointment_id
                            )
                            SELECT appointment_id, patient_id, status, start_offset_days, NULL
                            FROM appointment
                            """);
                }
                execute(statement, "DROP TABLE appointment");
                execute(statement, "ALTER TABLE appointment_next RENAME TO appointment");
                execute(statement, """
                        CREATE TRIGGER IF NOT EXISTS clinical_result_same_patient_insert
                        BEFORE INSERT ON clinical_result
                        FOR EACH ROW
                        WHEN NEW.patient_id <> (
                            SELECT patient_id FROM consultation WHERE consultation_id = NEW.consultation_id
                        )
                        BEGIN
                            SELECT RAISE(ABORT, 'result patient does not match consultation');
                        END
                        """);
                execute(statement, """
                        CREATE TABLE IF NOT EXISTS clinical_event (
                            event_id TEXT PRIMARY KEY,
                            patient_id TEXT NOT NULL REFERENCES patient(patient_id),
                            resource_type TEXT NOT NULL CHECK (resource_type IN ('consultation', 'appointment', 'result')),
                            resource_id TEXT NOT NULL,
                            change_type TEXT NOT NULL CHECK (change_type IN ('recorded', 'replaces')),
                            occurred_at TEXT,
                            detail TEXT NOT NULL
                        )
                        """);
                execute(statement, "INSERT INTO schema_marker (name) VALUES ('longitudinal-v2')");
                connection.commit();
            } catch (SQLException | RuntimeException failure) {
                connection.rollback();
                throw failure;
            } finally {
                connection.setAutoCommit(originalAutoCommit);
                statement.execute("PRAGMA foreign_keys=ON");
            }
        }
    }

    private static void execute(Statement statement, String sql) throws SQLException {
        statement.execute(sql);
    }

    private void createEventTable() {
        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS clinical_event (
                    event_id TEXT PRIMARY KEY,
                    patient_id TEXT NOT NULL REFERENCES patient(patient_id),
                    resource_type TEXT NOT NULL CHECK (resource_type IN ('consultation', 'appointment', 'result')),
                    resource_id TEXT NOT NULL,
                    change_type TEXT NOT NULL CHECK (change_type IN ('recorded', 'replaces')),
                    occurred_at TEXT,
                    detail TEXT NOT NULL
                )
                """);
    }

    private void addColumnIfAbsent(String table, String column, String definition) {
        if (!columnNames(table).contains(column)) {
            jdbc.execute("ALTER TABLE " + table + " ADD COLUMN " + column + " " + definition);
        }
    }

    private void backfillSyntheticCareClass() {
        jdbc.update(
                """
                UPDATE consultation
                SET care_class = ?
                WHERE consultation_id IN ('MHS-CON-001', 'MHS-CON-002', 'MHS-CON-003')
                  AND (care_class IS NULL OR TRIM(care_class) = '')
                """,
                SyntheticSeed.AMBULATORY_CARE);
    }

    private void backfillSyntheticResultStatus() {
        jdbc.update(
                """
                UPDATE clinical_result
                SET status = ?
                WHERE result_id IN (
                    'MHS-RES-001', 'MHS-RES-002', 'MHS-RES-003',
                    'MHS-RES-004', 'MHS-RES-005', 'MHS-RES-006'
                )
                  AND (status IS NULL OR TRIM(status) = '')
                """,
                SyntheticSeed.FINAL_RESULT);
    }

    private void backfillSyntheticBloodPressure() {
        for (SyntheticSeed.ComponentSeed component : SyntheticSeed.COMPONENTS) {
            jdbc.update(
                    """
                    INSERT INTO clinical_result_component (
                        component_id, result_id, component_name, value_decimal, unit
                    )
                    SELECT ?, result_id, ?, ?, ?
                    FROM clinical_result
                    WHERE result_id = ?
                      AND NOT EXISTS (
                          SELECT 1 FROM clinical_result_component WHERE component_id = ?
                      )
                    """,
                    component.componentId(),
                    component.name(),
                    component.valueDecimal(),
                    component.unit(),
                    component.resultId(),
                    component.componentId());
        }
    }

    private Set<String> columnNames(String table) {
        List<String> names = jdbc.query(
                "PRAGMA table_info(" + table + ")",
                (rs, row) -> rs.getString("name"));
        return new HashSet<>(names);
    }
}
