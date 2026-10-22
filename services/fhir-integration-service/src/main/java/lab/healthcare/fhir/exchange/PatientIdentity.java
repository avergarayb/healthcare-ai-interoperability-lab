package lab.healthcare.fhir.exchange;

import java.time.LocalDate;

/**
 * Patient identity for one exchange. Matching uses the identifier system and
 * value. The name fields travel only when a destination patient must be created.
 */
public record PatientIdentity(
        String identifierSystem,
        String identifierValue,
        String familyName,
        String givenName,
        LocalDate birthDate,
        String administrativeSex) {
}
