package lab.healthcare.minihis;

import java.util.List;

/**
 * Stable origin identifiers. A later FHIR transform must keep these ids;
 * they are not regenerated on startup or reset.
 */
public final class SyntheticSeed {

    /** Documented care classification of the current synthetic consultations. */
    public static final String AMBULATORY_CARE = "ambulatory";

    /** Documented status of the current synthetic results. */
    public static final String FINAL_RESULT = "final";

    public record PatientSeed(
            String patientId,
            String familyName,
            String givenName,
            String birthDate,
            String administrativeSex) {
    }

    public record ConsultationSeed(
            String consultationId,
            String patientId,
            String occurredAt,
            String reason,
            String clinicianName,
            String status,
            String careClass) {
    }

    public record ResultSeed(
            String resultId,
            String consultationId,
            String patientId,
            String resultType,
            String displayName,
            String valueText,
            String unit,
            String observedAt,
            String status) {
    }

    public record ComponentSeed(
            String componentId,
            String resultId,
            String name,
            String valueDecimal,
            String unit) {
    }

    public static final List<PatientSeed> PATIENTS = List.of(
            new PatientSeed("MHS-PAT-001", "Quispe", "Ana", "1984-03-12", "female"),
            new PatientSeed("MHS-PAT-002", "Vargas", "Luis", "1976-11-02", "male"),
            new PatientSeed("MHS-PAT-003", "Rojas", "Carmen", "1991-07-19", "female"));

    public static final List<ConsultationSeed> CONSULTATIONS = List.of(
            new ConsultationSeed(
                    "MHS-CON-001",
                    "MHS-PAT-001",
                    "2026-09-01T15:00:00Z",
                    "Control de laboratorio sintetico",
                    "Dra. Luz Demo",
                    "completed",
                    AMBULATORY_CARE),
            new ConsultationSeed(
                    "MHS-CON-002",
                    "MHS-PAT-002",
                    "2026-08-14T10:30:00Z",
                    "Revision de signos vitales sinteticos",
                    "Dr. Mateo Demo",
                    "completed",
                    AMBULATORY_CARE),
            new ConsultationSeed(
                    "MHS-CON-003",
                    "MHS-PAT-003",
                    "2026-07-20T18:45:00Z",
                    "Control sintetico de funcion renal",
                    "Dra. Nora Demo",
                    "completed",
                    AMBULATORY_CARE));

    public static final List<ResultSeed> RESULTS = List.of(
            new ResultSeed(
                    "MHS-RES-001",
                    "MHS-CON-001",
                    "MHS-PAT-001",
                    "laboratory",
                    "Hemoglobina",
                    "13.4",
                    "g/dL",
                    "2026-09-01T15:10:00Z",
                    FINAL_RESULT),
            new ResultSeed(
                    "MHS-RES-002",
                    "MHS-CON-001",
                    "MHS-PAT-001",
                    "vital_sign",
                    "Presion arterial",
                    "120/80",
                    "mmHg",
                    "2026-09-01T15:20:00Z",
                    FINAL_RESULT),
            new ResultSeed(
                    "MHS-RES-003",
                    "MHS-CON-002",
                    "MHS-PAT-002",
                    "laboratory",
                    "Glucosa",
                    "95",
                    "mg/dL",
                    "2026-08-14T10:40:00Z",
                    FINAL_RESULT),
            new ResultSeed(
                    "MHS-RES-004",
                    "MHS-CON-002",
                    "MHS-PAT-002",
                    "vital_sign",
                    "Frecuencia cardiaca",
                    "72",
                    "1/min",
                    "2026-08-14T10:50:00Z",
                    FINAL_RESULT),
            new ResultSeed(
                    "MHS-RES-005",
                    "MHS-CON-003",
                    "MHS-PAT-003",
                    "laboratory",
                    "Creatinina",
                    "0.8",
                    "mg/dL",
                    "2026-07-20T18:55:00Z",
                    FINAL_RESULT),
            new ResultSeed(
                    "MHS-RES-006",
                    "MHS-CON-003",
                    "MHS-PAT-003",
                    "vital_sign",
                    "Temperatura",
                    "36.6",
                    "C",
                    "2026-07-20T19:05:00Z",
                    FINAL_RESULT));

    /**
     * Structured parts of MHS-RES-002. They are stored explicitly and are not
     * derived from the descriptive value {@code 120/80}.
     */
    public static final List<ComponentSeed> COMPONENTS = List.of(
            new ComponentSeed("MHS-CMP-002-1", "MHS-RES-002", "Presion sistolica", "120", "mmHg"),
            new ComponentSeed("MHS-CMP-002-2", "MHS-RES-002", "Presion diastolica", "80", "mmHg"));

    private SyntheticSeed() {
    }
}
