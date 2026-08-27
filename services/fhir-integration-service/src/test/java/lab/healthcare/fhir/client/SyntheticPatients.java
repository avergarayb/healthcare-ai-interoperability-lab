package lab.healthcare.fhir.client;

import ca.uhn.fhir.rest.client.api.IGenericClient;
import org.hl7.fhir.r4.model.DateType;
import org.hl7.fhir.r4.model.Enumerations;
import org.hl7.fhir.r4.model.Patient;

public final class SyntheticPatients {

    static final String IDENTIFIER_SYSTEM = "https://example.org/lab/mrn";

    private SyntheticPatients() {
    }

    static Patient mariaGarcia() {
        return patient("patient-001", "MRN-10001", "Garcia", "Maria", Enumerations.AdministrativeGender.FEMALE, "1985-04-12");
    }

    static Patient juanGarcia() {
        return patient("patient-002", "MRN-10002", "Garcia", "Juan", Enumerations.AdministrativeGender.MALE, "1980-08-20");
    }

    static Patient mariaLopez() {
        return patient("patient-003", "MRN-10003", "Lopez", "Maria", Enumerations.AdministrativeGender.FEMALE, "1990-02-15");
    }

    public static void seed(IGenericClient fhirClient) {
        fhirClient.update().resource(mariaGarcia()).execute();
        fhirClient.update().resource(juanGarcia()).execute();
        fhirClient.update().resource(mariaLopez()).execute();
    }

    private static Patient patient(
            String logicalId,
            String mrn,
            String family,
            String given,
            Enumerations.AdministrativeGender gender,
            String birthDate) {
        Patient patient = new Patient();
        patient.setId(logicalId);
        patient.addIdentifier().setSystem(IDENTIFIER_SYSTEM).setValue(mrn);
        patient.addName().setFamily(family).addGiven(given);
        patient.setGender(gender);
        patient.setBirthDateElement(new DateType(birthDate));
        return patient;
    }
}
