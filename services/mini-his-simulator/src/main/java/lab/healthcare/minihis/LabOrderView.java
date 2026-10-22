package lab.healthcare.minihis;

public record LabOrderView(
        String orderId,
        String patientId,
        String destinationSystemKey,
        String testCode,
        String testDescription,
        String requestedAt,
        String localStatus,
        String correlationId,
        String destinationOrderId,
        String destinationOrganizationId) {
}
