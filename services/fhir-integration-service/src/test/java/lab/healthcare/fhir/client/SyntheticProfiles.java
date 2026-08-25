package lab.healthcare.fhir.client;

import ca.uhn.fhir.rest.client.api.IGenericClient;
import org.hl7.fhir.r4.model.ElementDefinition;
import org.hl7.fhir.r4.model.Enumerations;
import org.hl7.fhir.r4.model.StructureDefinition;

final class SyntheticProfiles {

    static final String LAB_BP_PROFILE_ID = "lab-blood-pressure-observation";
    static final String LAB_BP_PROFILE_URL =
            "https://example.org/fhir/StructureDefinition/lab-blood-pressure-observation";

    private SyntheticProfiles() {
    }

    static StructureDefinition labBloodPressureObservation() {
        StructureDefinition profile = new StructureDefinition();
        profile.setId(LAB_BP_PROFILE_ID);
        profile.setUrl(LAB_BP_PROFILE_URL);
        profile.setName("LabBloodPressureObservation");
        profile.setTitle("Lab Blood Pressure Observation");
        profile.setStatus(Enumerations.PublicationStatus.ACTIVE);
        profile.setExperimental(true);
        profile.setDescription(
                "Synthetic lab profile. Tightens Observation.subject and Observation.value[x] from 0..1 to 1..1.");
        profile.setFhirVersion(Enumerations.FHIRVersion._4_0_1);
        profile.setKind(StructureDefinition.StructureDefinitionKind.RESOURCE);
        profile.setAbstract(false);
        profile.setType("Observation");
        profile.setBaseDefinition("http://hl7.org/fhir/StructureDefinition/Observation");
        profile.setDerivation(StructureDefinition.TypeDerivationRule.CONSTRAINT);
        profile.getDifferential().addElement(element("Observation", "Observation", null, null));
        profile.getDifferential().addElement(element("Observation.subject", "Observation.subject", 1, "1"));
        profile.getDifferential().addElement(element("Observation.value[x]", "Observation.value[x]", 1, "1"));
        return profile;
    }

    private static ElementDefinition element(String id, String path, Integer min, String max) {
        ElementDefinition element = new ElementDefinition();
        element.setId(id);
        element.setPath(path);
        if (min != null) {
            element.setMin(min);
        }
        if (max != null) {
            element.setMax(max);
        }
        return element;
    }

    static void seed(IGenericClient fhirClient) {
        fhirClient.update().resource(labBloodPressureObservation()).execute();
    }
}
