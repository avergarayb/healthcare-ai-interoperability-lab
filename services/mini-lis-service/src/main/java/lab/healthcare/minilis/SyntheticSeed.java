package lab.healthcare.minilis;

import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Component;

import java.time.LocalDate;
import java.time.OffsetDateTime;

/**
 * Inserts the reproducible synthetic scenarios once. A restart does not add a second copy.
 */
@Component
class SyntheticSeed {

    static final String LABORATORY = "org-mini-lis";
    static final String REQUESTER = "org-mini-his";

    private final LaboratoryRecordService records;

    SyntheticSeed(LaboratoryRecordService records) {
        this.records = records;
    }

    @EventListener(ApplicationReadyEvent.class)
    public void load() {
        if (records.storedPatients() > 0) {
            return;
        }
        records.registerPatient(patient("EXT-PAT-001", "Lagos", "Marta", "1990-01-15", "female"), "MLS-PAT-001");
        records.registerPatient(patient("EXT-PAT-002", "Ramos", "Luis", "1978-06-02", "male"), "MLS-PAT-002");
        records.registerPatient(patient("EXT-PAT-003", "Paredes", "Nora", "2001-11-30", "female"), "MLS-PAT-003");

        records.createOrder(order("MLS-PAT-001", "EXT-REQ-001", "GLU", "Glucose", "2026-02-01T10:00:00Z"), "MLS-ORD-001");

        records.createOrder(order("MLS-PAT-002", "EXT-REQ-002", "HGB", "Hemoglobin", "2026-02-02T10:00:00Z"), "MLS-ORD-002");
        records.recordResult(result("MLS-ORD-002", "EXT-RES-002", "HGB", "13.5", "g/dL", "12.0-16.0", "2026-02-02T12:00:00Z"), "MLS-RES-002");
        records.complete("MLS-ORD-002");

        records.createOrder(order("MLS-PAT-003", "EXT-REQ-003", "PANEL", "Synthetic panel", "2026-02-03T10:00:00Z"), "MLS-ORD-003");
        records.recordResult(result("MLS-ORD-003", "EXT-RES-003", "GLU", "90", "mg/dL", "70-99", "2026-02-03T12:00:00Z"), "MLS-RES-003");
        records.recordResult(result("MLS-ORD-003", "EXT-RES-004", "HGB", "12.1", "g/dL", "12.0-16.0", "2026-02-03T12:05:00Z"), "MLS-RES-004");
        records.complete("MLS-ORD-003");
    }

    private static NewPatient patient(String externalId, String family, String given, String birthDate, String sex) {
        return new NewPatient(LABORATORY, externalId, family, given, LocalDate.parse(birthDate), sex);
    }

    private static NewOrder order(String patientId, String externalRequestId, String code, String description, String requestedAt) {
        return new NewOrder(patientId, REQUESTER, externalRequestId, code, description, OffsetDateTime.parse(requestedAt));
    }

    private static NewResult result(
            String orderId,
            String externalResultId,
            String code,
            String value,
            String unit,
            String range,
            String resultedAt) {
        return new NewResult(
                orderId,
                externalResultId,
                code,
                value,
                unit,
                range,
                OffsetDateTime.parse(resultedAt),
                ResultStatus.FINAL);
    }
}
