package lab.healthcare.fhir.client;

import ca.uhn.fhir.rest.client.api.IGenericClient;
import org.hl7.fhir.r4.model.DateType;
import org.hl7.fhir.r4.model.Enumerations;
import org.hl7.fhir.r4.model.Patient;

final class SyntheticHistoryPatients {

    static final String HISTORY_ID = "history-patient-001";
    static final String DELETE_ID = "history-delete-001";
    static final String IDENTIFIER_SYSTEM = "https://example.org/lab/mrn";
    static final String FAMILY = "History";
    static final String GIVEN_V1 = "V1";
    static final String GIVEN_V2 = "V2";
    static final String GIVEN_V3 = "V3";

    private SyntheticHistoryPatients() {
    }

    static void seed(IGenericClient fhirClient) {
        fhirClient.update().resource(patient(HISTORY_ID, "MRN-HIST-001", GIVEN_V1)).execute();
        fhirClient.update().resource(patient(HISTORY_ID, "MRN-HIST-001", GIVEN_V2)).execute();
        fhirClient.update().resource(patient(HISTORY_ID, "MRN-HIST-001", GIVEN_V3)).execute();
    }

    static Patient patient(String logicalId, String mrn, String given) {
        Patient patient = new Patient();
        patient.setId(logicalId);
        patient.addIdentifier().setSystem(IDENTIFIER_SYSTEM).setValue(mrn);
        patient.addName().setFamily(FAMILY).addGiven(given);
        patient.setGender(Enumerations.AdministrativeGender.FEMALE);
        patient.setBirthDateElement(new DateType("1988-03-21"));
        return patient;
    }
}
