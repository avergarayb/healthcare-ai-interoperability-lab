package lab.healthcare.fhir.client;

import ca.uhn.fhir.rest.client.api.IGenericClient;
import org.hl7.fhir.r4.model.Bundle;
import org.hl7.fhir.r4.model.Condition;
import org.hl7.fhir.r4.model.Observation;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestInstance;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import java.util.Set;
import java.util.stream.Collectors;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE)
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
class FhirResourcesAndReferencesIT {

    @Autowired
    private FhirService fhirService;

    @Autowired
    private IGenericClient fhirClient;

    @BeforeAll
    void seedSyntheticResources() {
        SyntheticPatients.seed(fhirClient);
        SyntheticClinicalResources.seed(fhirClient);
    }

    @Test
    void readObservationByLogicalId() {
        Observation observation = fhirService.readObservation("obs-001");

        assertThat(observation.getIdElement().getIdPart()).isEqualTo("obs-001");
        assertThat(fhirService.subjectReference(observation.getSubject())).isEqualTo("Patient/patient-001");
        assertThat(observation.getCode().getCodingFirstRep().getSystem()).isEqualTo("http://loinc.org");
        assertThat(observation.getCode().getCodingFirstRep().getCode()).isEqualTo("85354-9");
    }

    @Test
    void readConditionByLogicalId() {
        Condition condition = fhirService.readCondition("condition-001");

        assertThat(condition.getIdElement().getIdPart()).isEqualTo("condition-001");
        assertThat(fhirService.subjectReference(condition.getSubject())).isEqualTo("Patient/patient-001");
        assertThat(condition.getCode().getCodingFirstRep().getSystem()).isEqualTo("http://snomed.info/sct");
        assertThat(condition.getCode().getCodingFirstRep().getCode()).isEqualTo("38341003");
    }

    @Test
    void searchObservationsByPatientReturnsMatchingBundle() {
        Bundle bundle = fhirService.searchObservationsByPatient("patient-001");

        assertThat(bundle.getType()).isEqualTo(Bundle.BundleType.SEARCHSET);
        Set<String> ids = fhirService.extractObservations(bundle).stream()
                .map(observation -> observation.getIdElement().getIdPart())
                .collect(Collectors.toSet());

        assertThat(ids).contains("obs-001");
    }

    @Test
    void searchConditionsByPatientReturnsMatchingBundle() {
        Bundle bundle = fhirService.searchConditionsByPatient("patient-001");

        assertThat(bundle.getType()).isEqualTo(Bundle.BundleType.SEARCHSET);
        Set<String> ids = fhirService.extractConditions(bundle).stream()
                .map(condition -> condition.getIdElement().getIdPart())
                .collect(Collectors.toSet());

        assertThat(ids).contains("condition-001");
    }
}
