package lab.healthcare.minihis;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

import java.util.HashSet;
import java.util.List;
import java.util.Set;

@Component
public class MiniHisSchema {

    private final JdbcTemplate jdbc;

    public MiniHisSchema(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public void createIfAbsent() {
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
                    status TEXT NOT NULL CHECK (status IN ('completed', 'in_progress')),
                    care_class TEXT
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
                    observed_at TEXT NOT NULL,
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
        addColumnIfAbsent("consultation", "care_class", "TEXT");
        addColumnIfAbsent("clinical_result", "status", "TEXT");
        backfillSyntheticCareClass();
        backfillSyntheticResultStatus();
        backfillSyntheticBloodPressure();
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
