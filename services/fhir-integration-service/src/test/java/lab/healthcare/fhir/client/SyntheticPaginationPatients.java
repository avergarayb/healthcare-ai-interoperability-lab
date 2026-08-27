package lab.healthcare.fhir.client;

import ca.uhn.fhir.rest.client.api.IGenericClient;
import ca.uhn.fhir.rest.server.exceptions.BaseServerResponseException;
import org.hl7.fhir.r4.model.DateType;
import org.hl7.fhir.r4.model.Enumerations;
import org.hl7.fhir.r4.model.Patient;

import java.util.List;
import java.util.stream.IntStream;

final class SyntheticPaginationPatients {

    static final String FAMILY = "PageLab";
    static final String IDENTIFIER_SYSTEM = "https://example.org/lab/mrn";
    static final int COUNT = 12;

    private SyntheticPaginationPatients() {
    }

    static List<String> logicalIds() {
        return IntStream.rangeClosed(1, COUNT)
                .mapToObj(SyntheticPaginationPatients::logicalId)
                .toList();
    }

    static String logicalId(int index) {
        return "pagelab-patient-%03d".formatted(index);
    }

    static void seed(IGenericClient fhirClient) {
        for (int index = 1; index <= COUNT; index++) {
            deleteQuietly(fhirClient, "pagination-patient-%03d".formatted(index));
            fhirClient.update().resource(patient(index)).execute();
        }
    }

    private static void deleteQuietly(IGenericClient fhirClient, String logicalId) {
        try {
            fhirClient.delete().resourceById("Patient", logicalId).execute();
        } catch (BaseServerResponseException ignored) {
            // leftover IDs from an earlier seed may already be absent
        }
    }

    private static Patient patient(int index) {
        Patient patient = new Patient();
        patient.setId(logicalId(index));
        patient.addIdentifier().setSystem(IDENTIFIER_SYSTEM).setValue("MRN-PAG-%03d".formatted(index));
        patient.addName().setFamily(FAMILY).addGiven("P%03d".formatted(index));
        patient.setGender(Enumerations.AdministrativeGender.UNKNOWN);
        patient.setBirthDateElement(new DateType("1990-01-%02d".formatted(index)));
        return patient;
    }
}
