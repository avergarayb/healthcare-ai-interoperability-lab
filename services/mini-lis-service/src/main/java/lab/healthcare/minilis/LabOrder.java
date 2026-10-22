package lab.healthcare.minilis;

import java.time.OffsetDateTime;

public record LabOrder(
        String orderId,
        String patientId,
        String requestingOrganizationId,
        String externalRequestId,
        String testCode,
        String testDescription,
        OffsetDateTime requestedAt,
        OrderStatus status) {
}
