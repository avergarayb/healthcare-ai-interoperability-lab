package lab.healthcare.minihis;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

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
                    status TEXT NOT NULL CHECK (status IN ('completed', 'in_progress'))
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
                    observed_at TEXT NOT NULL
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
    }
}
