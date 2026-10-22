package lab.healthcare.minilis;

import java.time.OffsetDateTime;

public record LabResult(
        String resultId,
        String orderId,
        String patientId,
        String externalResultId,
        String testCode,
        String value,
        String unit,
        String referenceRange,
        OffsetDateTime resultedAt,
        ResultStatus status) {
}
