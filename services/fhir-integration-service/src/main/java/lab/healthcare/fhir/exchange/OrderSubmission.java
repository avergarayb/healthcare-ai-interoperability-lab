package lab.healthcare.fhir.exchange;

import java.time.OffsetDateTime;

public record OrderSubmission(
        String sourceOrganizationId,
        String destinationSystemKey,
        String externalRequestId,
        String testCode,
        String testDescription,
        OffsetDateTime requestedAt,
        PatientIdentity patient) {
}
