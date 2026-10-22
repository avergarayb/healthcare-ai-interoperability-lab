package lab.healthcare.fhir.exchange;

import java.time.OffsetDateTime;

public record OrderCorrelation(
        String correlationId,
        String sourceSystem,
        String sourceOrganizationId,
        String sourceOrderId,
        String destinationSystem,
        String destinationOrganizationId,
        String destinationOrderId,
        String destinationPatientId,
        String patientIdentifierSystem,
        String patientIdentifierValue,
        String testCode,
        String testDescription,
        OffsetDateTime requestedAt,
        String deliveryState,
        String errorCode) {
}
