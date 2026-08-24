package lab.healthcare.fhir.client;

import ca.uhn.fhir.rest.client.api.IGenericClient;
import org.hl7.fhir.r4.model.Bundle;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestInstance;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE)
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
class FhirSearchChainingIT {

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
    void chainedObservationByPatientNameReturnsObservationNotPatient() {
        Bundle bundle = fhirService.searchObservationsByPatientName("Maria");

        assertThat(bundle.getType()).isEqualTo(Bundle.BundleType.SEARCHSET);
        assertThat(fhirService.resourceIdentities(bundle)).contains("Observation/obs-001");
        assertThat(fhirService.extractPatients(bundle)).isEmpty();
    }

    @Test
    void chainedObservationByPatientNameAndCodeReturnsSeededObservation() {
        Bundle bundle = fhirService.searchObservationsByPatientNameAndCode("Maria", "85354-9");

        assertThat(bundle.getType()).isEqualTo(Bundle.BundleType.SEARCHSET);
        assertThat(fhirService.resourceIdentities(bundle)).contains("Observation/obs-001");
    }

    @Test
    void chainedConditionByPatientNameAndClinicalStatusReturnsSeededCondition() {
        Bundle bundle = fhirService.searchConditionsByPatientNameAndClinicalStatus("Maria", "active");

        assertThat(bundle.getType()).isEqualTo(Bundle.BundleType.SEARCHSET);
        assertThat(fhirService.resourceIdentities(bundle)).contains("Condition/condition-001");
    }

    @Test
    void chainedObservationByPatientIdentifierUsesBusinessMrn() {
        Bundle bundle = fhirService.searchObservationsByPatientIdentifier("MRN-10001");

        assertThat(bundle.getType()).isEqualTo(Bundle.BundleType.SEARCHSET);
        assertThat(fhirService.resourceIdentities(bundle)).contains("Observation/obs-001");
    }

    @Test
    void hasObservationCodeReturnsPatientWithoutObservation() {
        Bundle bundle = fhirService.searchPatientsHavingObservationCode("85354-9");

        assertThat(bundle.getType()).isEqualTo(Bundle.BundleType.SEARCHSET);
        assertThat(fhirService.resourceIdentities(bundle)).contains("Patient/patient-001");
        assertThat(fhirService.extractObservations(bundle)).isEmpty();
    }

    @Test
    void hasConditionClinicalStatusReturnsPatientWithoutCondition() {
        Bundle bundle = fhirService.searchPatientsHavingConditionClinicalStatus("active");

        assertThat(bundle.getType()).isEqualTo(Bundle.BundleType.SEARCHSET);
        assertThat(fhirService.resourceIdentities(bundle)).contains("Patient/patient-001");
        assertThat(fhirService.extractConditions(bundle)).isEmpty();
    }

    @Test
    void hasObservationCodeAndGenderUsesAndSemantics() {
        Bundle bundle = fhirService.searchPatientsHavingObservationCodeAndGender("85354-9", "female");

        assertThat(bundle.getType()).isEqualTo(Bundle.BundleType.SEARCHSET);
        assertThat(fhirService.resourceIdentities(bundle)).contains("Patient/patient-001");
        assertThat(fhirService.resourceIdentities(bundle)).doesNotContain("Patient/patient-002");
    }
}
