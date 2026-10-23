package lab.healthcare.minilis;

import java.time.LocalDate;
import java.time.OffsetDateTime;

public record OmlOrder(
        String messageControlId,
        String organizationId,
        String externalPatientId,
        String familyName,
        String givenName,
        LocalDate birthDate,
        String administrativeSex,
        String placerOrderId,
        String testCode,
        String testDescription,
        OffsetDateTime requestedAt) {
}
