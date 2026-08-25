package lab.healthcare.fhir.client;

import ca.uhn.fhir.rest.client.api.IGenericClient;
import org.hl7.fhir.r4.model.CodeSystem;
import org.hl7.fhir.r4.model.Enumerations;

final class SyntheticTerminology {

    static final String LAB_SYSTEM = "https://example.org/lab/observation-codes";
    static final String LAB_CODE = "lab-bp-panel";

    private SyntheticTerminology() {
    }

    static CodeSystem labObservationCodes() {
        CodeSystem codeSystem = new CodeSystem();
        codeSystem.setId("lab-observation-codes");
        codeSystem.setUrl(LAB_SYSTEM);
        codeSystem.setName("LabObservationCodes");
        codeSystem.setStatus(Enumerations.PublicationStatus.ACTIVE);
        codeSystem.setContent(CodeSystem.CodeSystemContentMode.COMPLETE);
        codeSystem.addConcept().setCode(LAB_CODE).setDisplay("Lab blood pressure panel");
        return codeSystem;
    }

    static void seed(IGenericClient fhirClient) {
        fhirClient.update().resource(labObservationCodes()).execute();
    }
}
