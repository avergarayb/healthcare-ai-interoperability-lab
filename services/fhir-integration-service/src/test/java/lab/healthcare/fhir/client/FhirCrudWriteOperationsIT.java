package lab.healthcare.fhir.client;

import ca.uhn.fhir.rest.api.MethodOutcome;
import ca.uhn.fhir.rest.client.api.IGenericClient;
import ca.uhn.fhir.rest.server.exceptions.BaseServerResponseException;
import org.hl7.fhir.r4.model.DateType;
import org.hl7.fhir.r4.model.Enumerations;
import org.hl7.fhir.r4.model.Observation;
import org.hl7.fhir.r4.model.Patient;
import org.hl7.fhir.r4.model.Quantity;
import org.hl7.fhir.r4.model.Reference;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestInstance;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE)
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
class FhirCrudWriteOperationsIT {

    static final String CLIENT_ASSIGNED_ID = "patient-write-001";

    @Autowired
    private FhirService fhirService;

    @Autowired
    private IGenericClient fhirClient;

    @BeforeAll
    void seedSyntheticPatients() {
        SyntheticPatients.seed(fhirClient);
    }

    @Test
    void patientLifecycleCreateReadUpdateDelete() {
        MethodOutcome created = fhirService.createPatient(anaTorres());
        String generatedId = fhirService.createdLogicalId(created);

        assertThat(generatedId).isNotBlank();
        assertThat(generatedId).isNotEqualTo(CLIENT_ASSIGNED_ID);
        assertThat(created.getCreated()).isTrue();

        Patient afterCreate = fhirService.readPatient(generatedId);
        assertThat(afterCreate.getNameFirstRep().getFamily()).isEqualTo("Torres");
        assertThat(afterCreate.getNameFirstRep().getGivenAsSingleString()).isEqualTo("Ana");
        assertThat(afterCreate.getIdentifierFirstRep().getValue()).isEqualTo("MRN-10004");

        afterCreate.getNameFirstRep().setFamily("Torres-Gomez");
        fhirService.updatePatient(afterCreate);

        Patient afterUpdate = fhirService.readPatient(generatedId);
        assertThat(afterUpdate.getNameFirstRep().getFamily()).isEqualTo("Torres-Gomez");
        assertThat(afterUpdate.getIdentifierFirstRep().getValue()).isEqualTo("MRN-10004");

        fhirService.deletePatient(generatedId);

        assertThatThrownBy(() -> fhirService.readPatient(generatedId))
                .isInstanceOf(FhirClientException.class)
                .cause()
                .isInstanceOf(BaseServerResponseException.class)
                .extracting(cause -> ((BaseServerResponseException) cause).getStatusCode())
                .isIn(404, 410);
    }

    @Test
    void putPatientAtClientAssignedLogicalId() {
        MethodOutcome outcome = fhirService.updatePatient(carlosMendoza());
        assertThat(fhirService.createdLogicalId(outcome)).isEqualTo(CLIENT_ASSIGNED_ID);

        Patient read = fhirService.readPatient(CLIENT_ASSIGNED_ID);
        assertThat(read.getIdElement().getIdPart()).isEqualTo(CLIENT_ASSIGNED_ID);
        assertThat(read.getNameFirstRep().getFamily()).isEqualTo("Mendoza");
        assertThat(read.getNameFirstRep().getGivenAsSingleString()).isEqualTo("Carlos");
        assertThat(read.getIdentifierFirstRep().getValue()).isEqualTo("MRN-10005");

        fhirService.deletePatient(CLIENT_ASSIGNED_ID);
    }

    @Test
    void createObservationPreservesSubjectAndLoinc() {
        String observationId = null;
        try {
            MethodOutcome created = fhirService.createObservation(bloodPressureForPatient001());
            observationId = fhirService.createdLogicalId(created);
            assertThat(observationId).isNotBlank();
            assertThat(observationId).isNotEqualTo("obs-001");
            assertThat(created.getCreated()).isTrue();

            Observation read = fhirService.readObservation(observationId);
            assertThat(fhirService.subjectReference(read.getSubject())).isEqualTo("Patient/patient-001");
            assertThat(read.getCode().getCodingFirstRep().getSystem()).isEqualTo("http://loinc.org");
            assertThat(read.getCode().getCodingFirstRep().getCode()).isEqualTo("85354-9");
            assertThat(read.getStatus()).isEqualTo(Observation.ObservationStatus.FINAL);
        } finally {
            if (observationId != null) {
                fhirService.deleteObservation(observationId);
            }
        }
    }

    private static Patient anaTorres() {
        Patient patient = new Patient();
        patient.addIdentifier().setSystem(SyntheticPatients.IDENTIFIER_SYSTEM).setValue("MRN-10004");
        patient.addName().setFamily("Torres").addGiven("Ana");
        patient.setGender(Enumerations.AdministrativeGender.FEMALE);
        patient.setBirthDateElement(new DateType("1992-06-10"));
        return patient;
    }

    private static Patient carlosMendoza() {
        Patient patient = new Patient();
        patient.setId(CLIENT_ASSIGNED_ID);
        patient.addIdentifier().setSystem(SyntheticPatients.IDENTIFIER_SYSTEM).setValue("MRN-10005");
        patient.addName().setFamily("Mendoza").addGiven("Carlos");
        patient.setGender(Enumerations.AdministrativeGender.MALE);
        patient.setBirthDateElement(new DateType("1978-11-03"));
        return patient;
    }

    private static Observation bloodPressureForPatient001() {
        Observation observation = new Observation();
        observation.setStatus(Observation.ObservationStatus.FINAL);
        observation.getCode().addCoding()
                .setSystem("http://loinc.org")
                .setCode("85354-9")
                .setDisplay("Blood pressure panel");
        observation.setSubject(new Reference("Patient/patient-001"));
        observation.setValue(new Quantity()
                .setValue(128)
                .setUnit("mmHg")
                .setSystem("http://unitsofmeasure.org")
                .setCode("mm[Hg]"));
        return observation;
    }
}
