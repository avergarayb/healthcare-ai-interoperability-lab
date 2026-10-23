package lab.healthcare.fhir.exchange;

import java.time.OffsetDateTime;

/**
 * Proprietary command derived from a canonical ServiceRequest. A destination
 * connector accepts this command. It is not a Mini LIS type.
 */
public record DestinationCommand(
        String patientId,
        String requestingOrganizationId,
        String externalRequestId,
        String testCode,
        String testDescription,
        OffsetDateTime requestedAt,
        String performerOrganizationId,
        String testSystem) {
}
