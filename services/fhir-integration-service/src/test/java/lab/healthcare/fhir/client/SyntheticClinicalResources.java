package lab.healthcare.fhir.client;

import ca.uhn.fhir.rest.client.api.IGenericClient;
import org.hl7.fhir.r4.model.CodeableConcept;
import org.hl7.fhir.r4.model.Coding;
import org.hl7.fhir.r4.model.Condition;
import org.hl7.fhir.r4.model.Observation;
import org.hl7.fhir.r4.model.Quantity;
import org.hl7.fhir.r4.model.Reference;

final class SyntheticClinicalResources {

    static final String PATIENT_REFERENCE = "Patient/patient-001";
    static final String LOINC = "http://loinc.org";
    static final String SNOMED_CT = "http://snomed.info/sct";

    private SyntheticClinicalResources() {
    }

    static Observation bloodPressurePanel() {
        Observation observation = new Observation();
        observation.setId("obs-001");
        observation.setStatus(Observation.ObservationStatus.FINAL);
        observation.setCode(new CodeableConcept().addCoding(new Coding()
                .setSystem(LOINC)
                .setCode("85354-9")
                .setDisplay("Blood pressure panel")));
        observation.setSubject(new Reference(PATIENT_REFERENCE));
        observation.setValue(new Quantity()
                .setValue(130)
                .setUnit("mmHg")
                .setSystem("http://unitsofmeasure.org")
                .setCode("mm[Hg]"));
        return observation;
    }

    static Condition hypertensiveDisorder() {
        Condition condition = new Condition();
        condition.setId("condition-001");
        condition.setClinicalStatus(new CodeableConcept().addCoding(new Coding()
                .setSystem("http://terminology.hl7.org/CodeSystem/condition-clinical")
                .setCode("active")));
        condition.setCode(new CodeableConcept().addCoding(new Coding()
                .setSystem(SNOMED_CT)
                .setCode("38341003")
                .setDisplay("Hypertensive disorder")));
        condition.setSubject(new Reference(PATIENT_REFERENCE));
        return condition;
    }

    static void seed(IGenericClient fhirClient) {
        fhirClient.update().resource(bloodPressurePanel()).execute();
        fhirClient.update().resource(hypertensiveDisorder()).execute();
    }
}
