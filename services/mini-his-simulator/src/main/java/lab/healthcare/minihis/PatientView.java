package lab.healthcare.minihis;

import java.util.List;

public record PatientView(
        String patientId,
        String familyName,
        String givenName,
        String birthDate,
        String administrativeSex,
        List<PatientIdentifierView> identifiers) {
}
