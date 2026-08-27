package lab.healthcare.fhir.client;

import lab.healthcare.fhir.exception.FhirClientException;

import ca.uhn.fhir.rest.client.api.IGenericClient;
import ca.uhn.fhir.rest.server.exceptions.BaseServerResponseException;
import org.hl7.fhir.r4.model.Bundle;
import org.hl7.fhir.r4.model.CodeableConcept;
import org.hl7.fhir.r4.model.Coding;
import org.hl7.fhir.r4.model.Observation;
import org.hl7.fhir.r4.model.Patient;
import org.hl7.fhir.r4.model.Quantity;
import org.hl7.fhir.r4.model.Reference;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestInstance;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE)
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
class FhirBundlesTransactionsIT {

    static final String MRN_SYSTEM = "https://example.org/lab/mrn";

    @Autowired
    private FhirService fhirService;

    @Autowired
    private IGenericClient fhirClient;

    @BeforeAll
    void seedSyntheticPatients() {
        SyntheticPatients.seed(fhirClient);
    }

    @Test
    void transactionCreatesPatientAndObservationWithResolvedReference() {
        Patient patient = newPatient("Vega", "Lucia");
        Observation observation = bloodPressure(null);
        Bundle request = fhirService.patientAndObservationCreateTransaction(patient, observation);

        Bundle response = fhirService.executeTransaction(request);

        assertThat(response.getType()).isEqualTo(Bundle.BundleType.TRANSACTIONRESPONSE);
        assertThat(fhirService.entryResponseStatuses(response))
                .allMatch(status -> status != null && status.startsWith("201"));

        String patientId = fhirService.logicalIdFromLocation(fhirService.entryResponseLocation(response, 0));
        String observationId = fhirService.logicalIdFromLocation(fhirService.entryResponseLocation(response, 1));
        Patient storedPatient = fhirService.readPatient(patientId);
        Observation storedObservation = fhirService.readObservation(observationId);

        assertThat(storedPatient.getNameFirstRep().getFamily()).isEqualTo("Vega");
        assertThat(fhirService.subjectReference(storedObservation.getSubject())).isEqualTo("Patient/" + patientId);
    }

    @Test
    void failedTransactionDoesNotPersistTheSuccessfulLookingEntry() {
        String identifier = "MRN-TX-" + UUID.randomUUID();
        Bundle request = new Bundle();
        request.setType(Bundle.BundleType.TRANSACTION);
        request.addEntry()
                .setResource(newPatientWithIdentifier("EtagTx", "ShouldRollback", identifier))
                .getRequest()
                .setMethod(Bundle.HTTPVerb.POST)
                .setUrl("Patient");
        request.addEntry()
                .setResource(fhirService.readPatient("patient-001"))
                .getRequest()
                .setMethod(Bundle.HTTPVerb.PUT)
                .setUrl("Patient/patient-001")
                .setIfMatch("W/\"999999\"");

        assertThatThrownBy(() -> fhirService.executeTransaction(request))
                .isInstanceOf(FhirClientException.class)
                .cause()
                .isInstanceOf(BaseServerResponseException.class)
                .extracting(cause -> ((BaseServerResponseException) cause).getStatusCode())
                .isEqualTo(409);

        assertThat(fhirService.extractPatients(fhirService.searchPatientsByIdentifier(identifier))).isEmpty();
        assertThat(fhirService.readPatient("patient-001").getNameFirstRep().getFamily()).isEqualTo("Garcia");
    }

    @Test
    void batchContinuesAfterAnIndependentFailure() {
        Patient patient = newPatient("Batch", "Nuria");
        Bundle request = fhirService.patientCreateAndGetBatch(patient, "patient-001");

        Bundle response = fhirService.executeBatch(request);

        assertThat(response.getType()).isEqualTo(Bundle.BundleType.BATCHRESPONSE);
        assertThat(fhirService.entryResponseStatuses(response).get(0)).startsWith("201");
        assertThat(fhirService.entryResponseStatuses(response).get(1)).startsWith("404");
        assertThat(fhirService.entryResponseStatuses(response).get(2)).startsWith("200");
        assertThat(response.getEntry().get(2).getResource()).isInstanceOf(Patient.class);
        assertThat(response.getEntry().get(2).getResource().getIdElement().getIdPart()).isEqualTo("patient-001");

        String createdId = fhirService.logicalIdFromLocation(fhirService.entryResponseLocation(response, 0));
        assertThat(fhirService.readPatient(createdId).getNameFirstRep().getFamily()).isEqualTo("Batch");
    }

    @Test
    void conditionalCreateReusesExistingPatientInsteadOfDuplicating() {
        Patient patient = newPatientWithIdentifier("ShouldNotDuplicate", "Maria", "MRN-10001");
        Bundle request = fhirService.conditionalCreatePatientTransaction(patient);

        Bundle response = fhirService.executeTransaction(request);

        assertThat(response.getType()).isEqualTo(Bundle.BundleType.TRANSACTIONRESPONSE);
        assertThat(fhirService.entryResponseStatuses(response).get(0)).startsWith("200");
        assertThat(fhirService.logicalIdFromLocation(fhirService.entryResponseLocation(response, 0)))
                .isEqualTo("patient-001");
        assertThat(fhirService.extractPatients(fhirService.searchPatientsByIdentifier("MRN-10001")))
                .extracting(found -> found.getIdElement().getIdPart())
                .containsExactly("patient-001");
    }

    @Test
    void searchsetBundleIsNotATransactionResponse() {
        Bundle searchset = fhirService.searchPatientsByName("Maria");
        Patient patient = newPatient("Tx", "Searchset");
        Bundle transactionResponse = fhirService.executeTransaction(
                fhirService.patientAndObservationCreateTransaction(patient, bloodPressure(null)));

        assertThat(searchset.getType()).isEqualTo(Bundle.BundleType.SEARCHSET);
        assertThat(transactionResponse.getType()).isEqualTo(Bundle.BundleType.TRANSACTIONRESPONSE);
        assertThat(fhirService.entryResponseStatuses(transactionResponse)).isNotEmpty();
    }

    private static Patient newPatient(String family, String given) {
        return newPatientWithIdentifier(family, given, "MRN-IT-" + UUID.randomUUID());
    }

    private static Patient newPatientWithIdentifier(String family, String given, String mrn) {
        Patient patient = new Patient();
        patient.addIdentifier().setSystem(MRN_SYSTEM).setValue(mrn);
        patient.addName().setFamily(family).addGiven(given);
        return patient;
    }

    private static Observation bloodPressure(String patientReference) {
        Observation observation = new Observation();
        observation.setStatus(Observation.ObservationStatus.FINAL);
        observation.setCode(new CodeableConcept().addCoding(new Coding()
                .setSystem("http://loinc.org")
                .setCode("85354-9")
                .setDisplay("Blood pressure panel")));
        if (patientReference != null) {
            observation.setSubject(new Reference(patientReference));
        }
        observation.setValue(new Quantity()
                .setValue(120)
                .setUnit("mmHg")
                .setSystem("http://unitsofmeasure.org")
                .setCode("mm[Hg]"));
        return observation;
    }
}
