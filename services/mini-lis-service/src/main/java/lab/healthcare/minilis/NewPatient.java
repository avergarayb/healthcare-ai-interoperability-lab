package lab.healthcare.minilis;

import java.time.LocalDate;
import java.time.OffsetDateTime;

public record NewPatient(
        String organizationId,
        String externalId,
        String familyName,
        String givenName,
        LocalDate birthDate,
        String administrativeSex) {
}

record NewOrder(
        String patientId,
        String requestingOrganizationId,
        String externalRequestId,
        String testCode,
        String testDescription,
        OffsetDateTime requestedAt) {
}

record NewResult(
        String orderId,
        String externalResultId,
        String testCode,
        String value,
        String unit,
        String referenceRange,
        OffsetDateTime resultedAt,
        ResultStatus status) {
}
