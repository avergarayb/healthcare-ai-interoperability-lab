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

    /** Proprietary appointment status. It is not a FHIR status. */
    public static final String NOT_ATTENDED = "not_attended";

    /** Proprietary appointment status. It is not a FHIR status. */
    public static final String CONFIRMED = "confirmed";

    /** Proprietary appointment status for a visit that already occurred. */
    public static final String APPOINTMENT_COMPLETED = "completed";

    /** Proprietary status shared by a planned consultation and a planned appointment. */
    public static final String SCHEDULED = "scheduled";

    /** Proprietary cancellation. It is not by itself a missed-visit trigger. */
    public static final String CANCELLED = "cancelled";

    /** Proprietary consultation status. It is not a FHIR status. */
    public static final String IN_PROGRESS = "in_progress";

    public static final String PRELIMINARY_RESULT = "preliminary";

    public static final String CORRECTED_RESULT = "corrected";

    /** Logical id system. It is not replaced by a follow-up case identifier. */
    public static final String PROPRIETARY_PATIENT_SYSTEM = "https://lab.local/mini-his/patient";

    /** Additional case identifier system. The value is a case id, not a patient id. */
    public static final String FOLLOW_UP_CASE_SYSTEM = "https://lab.local/followup-case";

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
            String careClass,
            String endedAt) {

        public ConsultationSeed(
                String consultationId,
                String patientId,
                String occurredAt,
                String reason,
                String clinicianName,
                String status,
                String careClass) {
            this(
                    consultationId,
                    patientId,
                    occurredAt,
                    reason,
                    clinicianName,
                    status,
                    careClass,
                    "completed".equals(status) ? occurredAt : null);
        }
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

    public record AppointmentSeed(
            String appointmentId,
            String patientId,
            String status,
            Integer startOffsetDays,
            String replacesAppointmentId) {

        public AppointmentSeed(String appointmentId, String patientId, String status, int startOffsetDays) {
            this(appointmentId, patientId, status, startOffsetDays, null);
        }
    }

    public record PatientIdentifierSeed(String system, String value, String patientId) {
    }

    public static final List<PatientSeed> PATIENTS = List.of(
            new PatientSeed("MHS-PAT-001", "Quispe", "Ana", "1984-03-12", "female"),
            new PatientSeed("MHS-PAT-002", "Vargas", "Luis", "1976-11-02", "male"),
            new PatientSeed("MHS-PAT-003", "Rojas", "Carmen", "1991-07-19", "female"),
            new PatientSeed("MHS-PAT-004", "Demo", "Nora", "1988-04-04", "female"),
            new PatientSeed("MHS-PAT-005", "Demo", "Raul", "1979-05-05", "male"),
            new PatientSeed("MHS-PAT-006", "Demo", "Ines", "1992-06-06", "female"),
            new PatientSeed("MHS-PAT-007", "Sosa", "Elena", "1985-01-07", "female"),
            new PatientSeed("MHS-PAT-008", "Paredes", "Marco", "1982-02-08", "male"),
            new PatientSeed("MHS-PAT-009", "Quispe", "Lia", "1990-03-09", "female"),
            new PatientSeed("MHS-PAT-010", "Vega", "Tomas", "1975-04-10", "male"),
            new PatientSeed("MHS-PAT-011", "Rios", "Ana", "1987-05-11", "female"),
            new PatientSeed("MHS-PAT-012", "Salas", "Pedro", "1993-06-12", "male"),
            new PatientSeed("MHS-PAT-013", "Leon", "Marta", "1980-07-13", "female"),
            new PatientSeed("MHS-PAT-014", "Cruz", "Diego", "1986-08-14", "male"),
            new PatientSeed("MHS-PAT-015", "Paz", "Rosa", "1994-09-15", "female"));

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
                    AMBULATORY_CARE),
            new ConsultationSeed(
                    "MHS-CON-015",
                    "MHS-PAT-006",
                    "2026-06-01T10:00:00Z",
                    "Control sintetico de hemoglobina",
                    "Dra. Luz Demo",
                    "completed",
                    AMBULATORY_CARE),
            consultation("MHS-CON-019", "MHS-PAT-010", "2026-03-01T10:00:00Z", "Control sintetico sin fecha de resultado", "2026-03-01T10:00:00Z"),
            consultation("MHS-CON-020", "MHS-PAT-011", "2026-04-01T10:00:00Z", "Control sintetico sin cierre", null),
            consultation("MHS-CON-021", "MHS-PAT-012", "2026-05-01T10:00:00Z", "Control sintetico sin laboratorio", "2026-05-01T10:00:00Z"),
            consultation("MHS-CON-022", "MHS-PAT-013", "2026-02-01T10:00:00Z", "Control sintetico con dos resultados", "2026-02-01T10:00:00Z"),
            consultation("MHS-CON-023", "MHS-PAT-014", "2026-01-15T10:00:00Z", "Control sintetico con resultado corregido", "2026-01-15T10:00:00Z"),
            consultation("MHS-CON-024", "MHS-PAT-015", "2024-06-01T10:00:00Z", "Control sintetico de 2024", "2024-06-01T10:00:00Z"),
            consultation("MHS-CON-025", "MHS-PAT-015", "2025-06-01T10:00:00Z", "Control sintetico de 2025", "2025-06-01T10:00:00Z"),
            new ConsultationSeed(
                    "MHS-CON-026", "MHS-PAT-015", "2026-06-01T10:00:00Z", "Control sintetico en curso",
                    "Dra. Luz Demo", IN_PROGRESS, AMBULATORY_CARE, null),
            new ConsultationSeed(
                    "MHS-CON-027", "MHS-PAT-015", "2023-06-01T10:00:00Z", "Control sintetico cancelado",
                    "Dra. Luz Demo", CANCELLED, AMBULATORY_CARE, null),
            new ConsultationSeed(
                    "MHS-CON-028", "MHS-PAT-015", "2026-12-01T10:00:00Z", "Control sintetico programado",
                    "Dra. Luz Demo", SCHEDULED, AMBULATORY_CARE, null));

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
                    FINAL_RESULT),
            new ResultSeed(
                    "MHS-RES-015",
                    "MHS-CON-015",
                    "MHS-PAT-006",
                    "laboratory",
                    "Hemoglobina",
                    "12.1",
                    "g/dL",
                    "2026-06-01T10:20:00Z",
                    FINAL_RESULT),
            result("MHS-RES-019", "MHS-CON-019", "MHS-PAT-010", "Hemoglobina", "11.0", "g/dL", null, FINAL_RESULT),
            result("MHS-RES-020", "MHS-CON-020", "MHS-PAT-011", "Glucosa", "90", "mg/dL", "2026-04-01T11:00:00Z", FINAL_RESULT),
            result("MHS-RES-022", "MHS-CON-022", "MHS-PAT-013", "Hemoglobina", "13.0", "g/dL", "2026-02-01T11:00:00Z", FINAL_RESULT),
            result("MHS-RES-023", "MHS-CON-022", "MHS-PAT-013", "Glucosa", "88", "mg/dL", "2026-02-01T12:00:00Z", FINAL_RESULT),
            result("MHS-RES-024", "MHS-CON-023", "MHS-PAT-014", "Hemoglobina", "10.0", "g/dL", "2026-01-15T11:00:00Z", PRELIMINARY_RESULT),
            result("MHS-RES-025", "MHS-CON-023", "MHS-PAT-014", "Hemoglobina", "10.4", "g/dL", "2026-01-15T12:00:00Z", CORRECTED_RESULT),
            result("MHS-RES-026", "MHS-CON-024", "MHS-PAT-015", "Hemoglobina", "12.5", "g/dL", "2024-06-01T12:00:00Z", FINAL_RESULT),
            result("MHS-RES-027", "MHS-CON-025", "MHS-PAT-015", "Glucosa", "100", "mg/dL", "2025-06-01T11:00:00Z", PRELIMINARY_RESULT),
            result("MHS-RES-028", "MHS-CON-025", "MHS-PAT-015", "Glucosa", "96", "mg/dL", "2025-06-01T13:00:00Z", FINAL_RESULT));

    /**
     * Structured parts of MHS-RES-002. They are stored explicitly and are not
     * derived from the descriptive value {@code 120/80}.
     */
    public static final List<ComponentSeed> COMPONENTS = List.of(
            new ComponentSeed("MHS-CMP-002-1", "MHS-RES-002", "Presion sistolica", "120", "mmHg"),
            new ComponentSeed("MHS-CMP-002-2", "MHS-RES-002", "Presion diastolica", "80", "mmHg"));

    /**
     * Offsets are the durable scenario. {@link AppointmentStart} resolves them
     * at read time, so startup does not update these rows and the past or
     * future relationship does not expire.
     */
    public static final List<AppointmentSeed> APPOINTMENTS = List.of(
            new AppointmentSeed("MHS-APT-001", "MHS-PAT-004", NOT_ATTENDED, AppointmentStart.PAST_OFFSET_DAYS),
            new AppointmentSeed("MHS-APT-003", "MHS-PAT-005", NOT_ATTENDED, AppointmentStart.PAST_OFFSET_DAYS),
            new AppointmentSeed("MHS-APT-002", "MHS-PAT-005", CONFIRMED, AppointmentStart.FUTURE_OFFSET_DAYS),
            new AppointmentSeed("MHS-APT-010", "MHS-PAT-007", NOT_ATTENDED, AppointmentStart.PAST_OFFSET_DAYS, null),
            new AppointmentSeed(
                    "MHS-APT-011", "MHS-PAT-007", CONFIRMED, AppointmentStart.FUTURE_OFFSET_DAYS, "MHS-APT-010"),
            new AppointmentSeed("MHS-APT-012", "MHS-PAT-008", CANCELLED, AppointmentStart.PAST_OFFSET_DAYS, null),
            new AppointmentSeed("MHS-APT-013", "MHS-PAT-009", NOT_ATTENDED, null, null),
            new AppointmentSeed("MHS-APT-020", "MHS-PAT-015", NOT_ATTENDED, AppointmentStart.PAST_OFFSET_DAYS, null),
            new AppointmentSeed(
                    "MHS-APT-021", "MHS-PAT-015", CONFIRMED, AppointmentStart.FUTURE_OFFSET_DAYS, "MHS-APT-020"),
            new AppointmentSeed("MHS-APT-022", "MHS-PAT-015", CANCELLED, -30, null),
            new AppointmentSeed("MHS-APT-023", "MHS-PAT-015", APPOINTMENT_COMPLETED, -200, null),
            new AppointmentSeed("MHS-APT-024", "MHS-PAT-015", SCHEDULED, 30, null));

    public static final List<PatientIdentifierSeed> PATIENT_IDENTIFIERS = List.of(
            new PatientIdentifierSeed(FOLLOW_UP_CASE_SYSTEM, "SYN-FOLLOWUP-013", "MHS-PAT-004"),
            new PatientIdentifierSeed(FOLLOW_UP_CASE_SYSTEM, "SYN-FOLLOWUP-014", "MHS-PAT-005"),
            new PatientIdentifierSeed(FOLLOW_UP_CASE_SYSTEM, "SYN-FOLLOWUP-015", "MHS-PAT-006"),
            new PatientIdentifierSeed(FOLLOW_UP_CASE_SYSTEM, "SYN-FOLLOWUP-016", "MHS-PAT-007"),
            new PatientIdentifierSeed(FOLLOW_UP_CASE_SYSTEM, "SYN-FOLLOWUP-017", "MHS-PAT-008"),
            new PatientIdentifierSeed(FOLLOW_UP_CASE_SYSTEM, "SYN-FOLLOWUP-018", "MHS-PAT-009"),
            new PatientIdentifierSeed(FOLLOW_UP_CASE_SYSTEM, "SYN-FOLLOWUP-019", "MHS-PAT-010"),
            new PatientIdentifierSeed(FOLLOW_UP_CASE_SYSTEM, "SYN-FOLLOWUP-020", "MHS-PAT-011"),
            new PatientIdentifierSeed(FOLLOW_UP_CASE_SYSTEM, "SYN-FOLLOWUP-021", "MHS-PAT-012"),
            new PatientIdentifierSeed(FOLLOW_UP_CASE_SYSTEM, "SYN-FOLLOWUP-022", "MHS-PAT-013"),
            new PatientIdentifierSeed(FOLLOW_UP_CASE_SYSTEM, "SYN-FOLLOWUP-023", "MHS-PAT-014"),
            new PatientIdentifierSeed(FOLLOW_UP_CASE_SYSTEM, "SYN-FOLLOWUP-024", "MHS-PAT-015"));

    public static boolean backfilledConsultation(String consultationId) {
        return consultationId != null && consultationId.compareTo("MHS-CON-019") >= 0;
    }

    public static boolean backfilledResult(String resultId) {
        return resultId != null && resultId.compareTo("MHS-RES-019") >= 0;
    }

    public static boolean backfilledAppointment(String appointmentId) {
        return appointmentId != null && appointmentId.compareTo("MHS-APT-010") >= 0;
    }

    public static boolean backfilledPatient(String patientId) {
        return patientId != null && patientId.compareTo("MHS-PAT-007") >= 0;
    }

    public static boolean backfilledIdentifier(String value) {
        return value != null && value.compareTo("SYN-FOLLOWUP-016") >= 0;
    }

    private static ConsultationSeed consultation(
            String consultationId, String patientId, String occurredAt, String reason, String endedAt) {
        return new ConsultationSeed(
                consultationId,
                patientId,
                occurredAt,
                reason,
                "Dra. Luz Demo",
                "completed",
                AMBULATORY_CARE,
                endedAt);
    }

    private static ResultSeed result(
            String resultId,
            String consultationId,
            String patientId,
            String displayName,
            String valueText,
            String unit,
            String observedAt,
            String status) {
        return new ResultSeed(
                resultId, consultationId, patientId, "laboratory", displayName, valueText, unit, observedAt, status);
    }

    private SyntheticSeed() {
    }
}
