package lab.healthcare.minihis;

import org.junit.jupiter.api.Test;
import org.sqlite.SQLiteConfig;
import org.sqlite.SQLiteDataSource;
import org.springframework.jdbc.core.JdbcTemplate;

import java.nio.file.Files;
import java.nio.file.Path;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class MiniHisSchemaMigrationTest {

    @Test
    void addsMissingColumnsAndFillsOnlyBlankSyntheticRows() throws Exception {
        Path database = Files.createTempFile("mini-his-legacy", ".sqlite");
        try {
            JdbcTemplate jdbc = jdbc(database);
            createLegacySchema(jdbc);
            jdbc.update(
                    """
                    INSERT INTO patient (patient_id, family_name, given_name, birth_date, administrative_sex)
                    VALUES ('MHS-PAT-001', 'Quispe', 'Ana', '1984-03-12', 'female'),
                           ('LOCAL-PAT-9', 'Local', 'Paz', '1990-01-01', 'female')
                    """);
            jdbc.update(
                    """
                    INSERT INTO consultation (
                        consultation_id, patient_id, occurred_at, reason, clinician_name, status
                    ) VALUES
                    ('MHS-CON-001', 'MHS-PAT-001', '2026-09-01T15:00:00Z', 'Control', 'Dra. Luz Demo', 'completed'),
                    ('LOCAL-CON-9', 'LOCAL-PAT-9', '2026-09-02T15:00:00Z', 'Local', 'Dr. Local', 'in_progress')
                    """);
            jdbc.update(
                    """
                    INSERT INTO clinical_result (
                        result_id, consultation_id, patient_id, result_type, display_name,
                        value_text, unit, observed_at
                    ) VALUES
                    ('MHS-RES-001', 'MHS-CON-001', 'MHS-PAT-001', 'laboratory', 'Hemoglobina', '13.4', 'g/dL', '2026-09-01T15:10:00Z'),
                    ('LOCAL-RES-9', 'LOCAL-CON-9', 'LOCAL-PAT-9', 'laboratory', 'Nota', '1', '', '2026-09-02T15:10:00Z')
                    """);
            int patients = count(jdbc, "patient");
            int consultations = count(jdbc, "consultation");
            int results = count(jdbc, "clinical_result");

            MiniHisSchema schema = new MiniHisSchema(jdbc);
            schema.createIfAbsent();

            assertThat(count(jdbc, "patient")).isEqualTo(patients + patientsAtOrAfter004());
            assertThat(count(jdbc, "consultation")).isEqualTo(consultations + backfilledConsultations());
            assertThat(count(jdbc, "clinical_result")).isEqualTo(results + backfilledResults());
            assertThat(text(jdbc, "SELECT care_class FROM consultation WHERE consultation_id = 'MHS-CON-001'"))
                    .isEqualTo(SyntheticSeed.AMBULATORY_CARE);
            assertThat(text(jdbc, "SELECT status FROM clinical_result WHERE result_id = 'MHS-RES-001'"))
                    .isEqualTo(SyntheticSeed.FINAL_RESULT);
            assertThat(text(jdbc, "SELECT care_class FROM consultation WHERE consultation_id = 'LOCAL-CON-9'"))
                    .isNull();
            assertThat(text(jdbc, "SELECT status FROM clinical_result WHERE result_id = 'LOCAL-RES-9'"))
                    .isNull();

            jdbc.update("UPDATE consultation SET care_class = 'specialist' WHERE consultation_id = 'MHS-CON-001'");
            schema.createIfAbsent();

            assertThat(text(jdbc, "SELECT care_class FROM consultation WHERE consultation_id = 'MHS-CON-001'"))
                    .isEqualTo("specialist");
            assertThat(text(jdbc, "SELECT care_class FROM consultation WHERE consultation_id = 'LOCAL-CON-9'"))
                    .isNull();
            assertThat(count(jdbc, "patient")).isEqualTo(patients + patientsAtOrAfter004());
        } finally {
            Files.deleteIfExists(database);
        }
    }

    @Test
    void bloodPressureComponentsFillOnlyTheSyntheticResult() throws Exception {
        Path database = Files.createTempFile("mini-his-pressure", ".sqlite");
        try {
            JdbcTemplate jdbc = jdbc(database);
            createLegacySchema(jdbc);
            jdbc.update(
                    """
                    INSERT INTO patient (patient_id, family_name, given_name, birth_date, administrative_sex)
                    VALUES ('MHS-PAT-001', 'Quispe', 'Ana', '1984-03-12', 'female'),
                           ('LOCAL-PAT-9', 'Local', 'Paz', '1990-01-01', 'female')
                    """);
            jdbc.update(
                    """
                    INSERT INTO consultation (
                        consultation_id, patient_id, occurred_at, reason, clinician_name, status
                    ) VALUES
                    ('MHS-CON-001', 'MHS-PAT-001', '2026-09-01T15:00:00Z', 'Control', 'Dra. Luz Demo', 'completed'),
                    ('LOCAL-CON-9', 'LOCAL-PAT-9', '2026-09-02T15:00:00Z', 'Local', 'Dr. Local', 'completed')
                    """);
            jdbc.update(
                    """
                    INSERT INTO clinical_result (
                        result_id, consultation_id, patient_id, result_type, display_name,
                        value_text, unit, observed_at
                    ) VALUES
                    ('MHS-RES-001', 'MHS-CON-001', 'MHS-PAT-001', 'laboratory', 'Hemoglobina', '13.4', 'g/dL', '2026-09-01T15:10:00Z'),
                    ('MHS-RES-002', 'MHS-CON-001', 'MHS-PAT-001', 'vital_sign', 'Presion arterial', '120/80', 'mmHg', '2026-09-01T15:20:00Z'),
                    ('LOCAL-RES-9', 'LOCAL-CON-9', 'LOCAL-PAT-9', 'vital_sign', 'Presion arterial', '120/80', 'mmHg', '2026-09-02T15:20:00Z')
                    """);

            MiniHisSchema schema = new MiniHisSchema(jdbc);
            schema.createIfAbsent();
            schema.createIfAbsent();

            assertThat(text(jdbc, "SELECT value_text FROM clinical_result WHERE result_id = 'MHS-RES-002'"))
                    .isEqualTo("120/80");
            assertThat(count(jdbc, "clinical_result_component")).isEqualTo(2);
            assertThat(text(jdbc, "SELECT component_name FROM clinical_result_component WHERE component_id = 'MHS-CMP-002-1'"))
                    .isEqualTo("Presion sistolica");
            assertThat(text(jdbc, "SELECT value_decimal FROM clinical_result_component WHERE component_id = 'MHS-CMP-002-1'"))
                    .isEqualTo("120");
            assertThat(text(jdbc, "SELECT unit FROM clinical_result_component WHERE component_id = 'MHS-CMP-002-2'"))
                    .isEqualTo("mmHg");
            assertThat(text(jdbc, "SELECT value_decimal FROM clinical_result_component WHERE component_id = 'MHS-CMP-002-2'"))
                    .isEqualTo("80");
            assertThat(countWhere(jdbc, "clinical_result_component", "result_id = 'MHS-RES-001'")).isZero();
            assertThat(countWhere(jdbc, "clinical_result_component", "result_id = 'LOCAL-RES-9'")).isZero();

            jdbc.update("UPDATE clinical_result_component SET value_decimal = '119' WHERE component_id = 'MHS-CMP-002-1'");
            schema.createIfAbsent();

            assertThat(text(jdbc, "SELECT value_decimal FROM clinical_result_component WHERE component_id = 'MHS-CMP-002-1'"))
                    .isEqualTo("119");
            assertThat(count(jdbc, "clinical_result_component")).isEqualTo(2);
            assertThat(count(jdbc, "clinical_result")).isEqualTo(3 + backfilledResults());
        } finally {
            Files.deleteIfExists(database);
        }
    }

    @Test
    void appointmentOffsetsAreInsertedOnceAndNeverRewritten() throws Exception {
        Path database = Files.createTempFile("mini-his-appointments", ".sqlite");
        try {
            JdbcTemplate jdbc = jdbc(database);
            createLegacySchema(jdbc);
            jdbc.update(
                    """
                    INSERT INTO patient (patient_id, family_name, given_name, birth_date, administrative_sex)
                    VALUES ('MHS-PAT-001', 'Quispe', 'Ana', '1984-03-12', 'female'),
                           ('LOCAL-PAT-9', 'Local', 'Paz', '1990-01-01', 'female')
                    """);

            MiniHisSchema schema = new MiniHisSchema(jdbc);
            schema.createIfAbsent();
            jdbc.update(
                    """
                    INSERT INTO appointment (appointment_id, patient_id, status, start_offset_days)
                    VALUES ('LOCAL-APT-9', 'LOCAL-PAT-9', 'confirmed', 12)
                    """);
            jdbc.update("UPDATE appointment SET start_offset_days = -7 WHERE appointment_id = 'MHS-APT-001'");
            jdbc.update("UPDATE patient SET family_name = 'Conservada' WHERE patient_id = 'MHS-PAT-004'");
            schema.createIfAbsent();

            assertThat(jdbc.queryForObject(
                    "SELECT start_offset_days FROM appointment WHERE appointment_id = 'MHS-APT-001'", Integer.class))
                    .isEqualTo(-7);
            assertThat(text(jdbc, "SELECT status FROM appointment WHERE appointment_id = 'MHS-APT-001'"))
                    .isEqualTo(SyntheticSeed.NOT_ATTENDED);
            assertThat(jdbc.queryForObject(
                    "SELECT start_offset_days FROM appointment WHERE appointment_id = 'LOCAL-APT-9'", Integer.class))
                    .isEqualTo(12);
            assertThat(text(jdbc, "SELECT family_name FROM patient WHERE patient_id = 'MHS-PAT-004'"))
                    .isEqualTo("Conservada");
            assertThat(text(jdbc, "SELECT family_name FROM patient WHERE patient_id = 'MHS-PAT-001'"))
                    .isEqualTo("Quispe");
            assertThat(countWhere(jdbc, "appointment", "patient_id = 'MHS-PAT-001'")).isZero();
            assertThat(countWhere(jdbc, "appointment", "patient_id = 'MHS-PAT-004'")).isEqualTo(1);
            assertThat(countWhere(jdbc, "appointment", "patient_id = 'MHS-PAT-005'")).isEqualTo(2);
            assertThat(count(jdbc, "appointment")).isEqualTo(4 + backfilledAppointments());
            assertThat(count(jdbc, "patient")).isEqualTo(5 + backfilledPatients());
        } finally {
            Files.deleteIfExists(database);
        }
    }

    @Test
    void followUpIdentifiersAreInsertedOnceAndNeverReassigned() throws Exception {
        Path database = Files.createTempFile("mini-his-case", ".sqlite");
        try {
            JdbcTemplate jdbc = jdbc(database);
            createLegacySchema(jdbc);
            jdbc.update(
                    """
                    INSERT INTO patient (patient_id, family_name, given_name, birth_date, administrative_sex)
                    VALUES ('MHS-PAT-001', 'Quispe', 'Ana', '1984-03-12', 'female'),
                           ('LOCAL-PAT-9', 'Local', 'Paz', '1990-01-01', 'female')
                    """);

            MiniHisSchema schema = new MiniHisSchema(jdbc);
            schema.createIfAbsent();
            schema.createIfAbsent();

            assertThat(count(jdbc, "patient_identifier")).isEqualTo(SyntheticSeed.PATIENT_IDENTIFIERS.size());
            assertThat(text(jdbc, "SELECT patient_id FROM patient_identifier WHERE identifier_value = 'SYN-FOLLOWUP-013'"))
                    .isEqualTo("MHS-PAT-004");
            assertThat(text(jdbc, "SELECT patient_id FROM patient_identifier WHERE identifier_value = 'SYN-FOLLOWUP-014'"))
                    .isEqualTo("MHS-PAT-005");
            assertThat(text(jdbc, "SELECT patient_id FROM patient_identifier WHERE identifier_value = 'SYN-FOLLOWUP-015'"))
                    .isEqualTo("MHS-PAT-006");
            assertThat(countWhere(jdbc, "patient_identifier", "patient_id = 'MHS-PAT-001'")).isZero();
            assertThat(countWhere(
                    jdbc,
                    "patient_identifier",
                    "identifier_value IN ('SYN-FOLLOWUP-001','SYN-FOLLOWUP-002','SYN-FOLLOWUP-003','SYN-FOLLOWUP-004','SYN-FOLLOWUP-005','SYN-FOLLOWUP-006','SYN-FOLLOWUP-007','SYN-FOLLOWUP-008','SYN-FOLLOWUP-009','SYN-FOLLOWUP-010','SYN-FOLLOWUP-011','SYN-FOLLOWUP-012')"))
                    .isZero();
            assertThat(countWhere(jdbc, "consultation", "patient_id = 'MHS-PAT-006'")).isZero();
            assertThat(countWhere(jdbc, "appointment", "patient_id = 'MHS-PAT-006'")).isZero();

            jdbc.update(
                    """
                    UPDATE patient_identifier
                    SET patient_id = 'LOCAL-PAT-9'
                    WHERE identifier_system = ? AND identifier_value = 'SYN-FOLLOWUP-013'
                    """,
                    SyntheticSeed.FOLLOW_UP_CASE_SYSTEM);
            schema.createIfAbsent();

            assertThat(count(jdbc, "patient_identifier")).isEqualTo(SyntheticSeed.PATIENT_IDENTIFIERS.size());
            assertThat(text(jdbc, "SELECT patient_id FROM patient_identifier WHERE identifier_value = 'SYN-FOLLOWUP-013'"))
                    .isEqualTo("LOCAL-PAT-9");
            assertThatThrownBy(() -> jdbc.update(
                    """
                    INSERT INTO patient_identifier (identifier_system, identifier_value, patient_id)
                    VALUES (?, 'SYN-FOLLOWUP-013', 'MHS-PAT-004')
                    """,
                    SyntheticSeed.FOLLOW_UP_CASE_SYSTEM))
                    .isInstanceOf(org.springframework.dao.DataAccessException.class);
        } finally {
            Files.deleteIfExists(database);
        }
    }

    private static JdbcTemplate jdbc(Path database) {
        SQLiteConfig config = new SQLiteConfig();
        config.enforceForeignKeys(true);
        SQLiteDataSource dataSource = new SQLiteDataSource(config);
        dataSource.setUrl("jdbc:sqlite:" + database.toAbsolutePath());
        return new JdbcTemplate(dataSource);
    }

    private static void createLegacySchema(JdbcTemplate jdbc) {
        jdbc.execute("""
                CREATE TABLE patient (
                    patient_id TEXT PRIMARY KEY,
                    family_name TEXT NOT NULL,
                    given_name TEXT NOT NULL,
                    birth_date TEXT NOT NULL,
                    administrative_sex TEXT NOT NULL
                )
                """);
        jdbc.execute("""
                CREATE TABLE consultation (
                    consultation_id TEXT PRIMARY KEY,
                    patient_id TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    clinician_name TEXT NOT NULL,
                    status TEXT NOT NULL
                )
                """);
        jdbc.execute("""
                CREATE TABLE clinical_result (
                    result_id TEXT PRIMARY KEY,
                    consultation_id TEXT NOT NULL,
                    patient_id TEXT NOT NULL,
                    result_type TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    value_text TEXT NOT NULL,
                    unit TEXT NOT NULL,
                    observed_at TEXT NOT NULL
                )
                """);
    }

    private static int patientsAtOrAfter004() {
        return (int) SyntheticSeed.PATIENTS.stream()
                .filter(patient -> patient.patientId().compareTo("MHS-PAT-004") >= 0)
                .count();
    }

    private static int backfilledPatients() {
        return (int) SyntheticSeed.PATIENTS.stream()
                .filter(patient -> SyntheticSeed.backfilledPatient(patient.patientId()))
                .count();
    }

    private static int backfilledConsultations() {
        return (int) SyntheticSeed.CONSULTATIONS.stream()
                .filter(consultation -> SyntheticSeed.backfilledConsultation(consultation.consultationId()))
                .count();
    }

    private static int backfilledResults() {
        return (int) SyntheticSeed.RESULTS.stream()
                .filter(result -> SyntheticSeed.backfilledResult(result.resultId()))
                .count();
    }

    private static int backfilledAppointments() {
        return (int) SyntheticSeed.APPOINTMENTS.stream()
                .filter(appointment -> SyntheticSeed.backfilledAppointment(appointment.appointmentId()))
                .count();
    }

    private static int count(JdbcTemplate jdbc, String table) {
        return countWhere(jdbc, table, "1 = 1");
    }

    private static int countWhere(JdbcTemplate jdbc, String table, String where) {
        Integer count = jdbc.queryForObject("SELECT COUNT(*) FROM " + table + " WHERE " + where, Integer.class);
        return count == null ? 0 : count;
    }

    private static String text(JdbcTemplate jdbc, String sql) {
        return jdbc.queryForObject(sql, String.class);
    }
}
