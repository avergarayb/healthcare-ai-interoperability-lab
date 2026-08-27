package lab.healthcare.fhir.client;

import ca.uhn.fhir.rest.client.api.IGenericClient;
import org.hl7.fhir.r4.model.CodeableConcept;
import org.hl7.fhir.r4.model.Coding;
import org.hl7.fhir.r4.model.DateTimeType;
import org.hl7.fhir.r4.model.Encounter;
import org.hl7.fhir.r4.model.MedicationRequest;
import org.hl7.fhir.r4.model.Observation;
import org.hl7.fhir.r4.model.Quantity;
import org.hl7.fhir.r4.model.Reference;

final class SyntheticEverythingResources {

    static final String PATIENT_ID = "patient-001";
    static final String PATIENT_REFERENCE = "Patient/patient-001";
    static final String ENCOUNTER_ID = "encounter-001";
    static final String MEDICATION_REQUEST_ID = "medreq-001";
    static final String DATED_OBSERVATION_ID = "everything-obs-dated";

    private SyntheticEverythingResources() {
    }

    static Encounter ambulatoryEncounter() {
        Encounter encounter = new Encounter();
        encounter.setId(ENCOUNTER_ID);
        encounter.setStatus(Encounter.EncounterStatus.FINISHED);
        encounter.setClass_(new Coding()
                .setSystem("http://terminology.hl7.org/CodeSystem/v3-ActCode")
                .setCode("AMB")
                .setDisplay("ambulatory"));
        encounter.setSubject(new Reference(PATIENT_REFERENCE));
        return encounter;
    }

    static MedicationRequest lisinopril() {
        MedicationRequest request = new MedicationRequest();
        request.setId(MEDICATION_REQUEST_ID);
        request.setStatus(MedicationRequest.MedicationRequestStatus.ACTIVE);
        request.setIntent(MedicationRequest.MedicationRequestIntent.ORDER);
        request.setMedication(new CodeableConcept().addCoding(new Coding()
                .setSystem("http://www.nlm.nih.gov/research/umls/rxnorm")
                .setCode("314076")
                .setDisplay("Lisinopril 10 MG Oral Tablet")));
        request.setSubject(new Reference(PATIENT_REFERENCE));
        return request;
    }

    static Observation datedHeartRate() {
        Observation observation = new Observation();
        observation.setId(DATED_OBSERVATION_ID);
        observation.setStatus(Observation.ObservationStatus.FINAL);
        observation.setCode(new CodeableConcept().addCoding(new Coding()
                .setSystem(SyntheticClinicalResources.LOINC)
                .setCode("8867-4")
                .setDisplay("Heart rate")));
        observation.setSubject(new Reference(PATIENT_REFERENCE));
        observation.setEffective(new DateTimeType("2020-06-15T10:00:00Z"));
        observation.setValue(new Quantity()
                .setValue(72)
                .setUnit("/min")
                .setSystem("http://unitsofmeasure.org")
                .setCode("/min"));
        return observation;
    }

    static void seed(IGenericClient fhirClient) {
        fhirClient.update().resource(ambulatoryEncounter()).execute();
        fhirClient.update().resource(lisinopril()).execute();
        fhirClient.update().resource(datedHeartRate()).execute();
    }
}
