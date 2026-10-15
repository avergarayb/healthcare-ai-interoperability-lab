package lab.healthcare.minihis;

public record PatientView(
        String patientId,
        String familyName,
        String givenName,
        String birthDate,
        String administrativeSex) {
}
