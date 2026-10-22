package lab.healthcare.minilis;

import java.time.LocalDate;

public record ExternalPatient(
        String patientId,
        String organizationId,
        String externalId,
        String familyName,
        String givenName,
        LocalDate birthDate,
        String administrativeSex) {
}
