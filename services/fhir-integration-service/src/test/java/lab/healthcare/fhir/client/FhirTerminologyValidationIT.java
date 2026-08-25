package lab.healthcare.fhir.client;

import ca.uhn.fhir.rest.client.api.IGenericClient;
import org.hl7.fhir.r4.model.Bundle;
import org.hl7.fhir.r4.model.Coding;
import org.hl7.fhir.r4.model.Condition;
import org.hl7.fhir.r4.model.Observation;
import org.hl7.fhir.r4.model.Parameters;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestInstance;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE)
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
class FhirTerminologyValidationIT {

    static final String LOINC = "http://loinc.org";
    static final String SNOMED = "http://snomed.info/sct";

    @Autowired
    private FhirService fhirService;

    @Autowired
    private IGenericClient fhirClient;

    @BeforeAll
    void seedSyntheticResources() {
        SyntheticPatients.seed(fhirClient);
        SyntheticClinicalResources.seed(fhirClient);
        SyntheticTerminology.seed(fhirClient);
    }

    @Test
    void observationCodeIsLoincCodeableConcept() {
        Observation observation = fhirService.readObservation("obs-001");
        Coding coding = fhirService.primaryCoding(observation.getCode());

        assertThat(coding.getSystem()).isEqualTo(LOINC);
        assertThat(coding.getCode()).isEqualTo("85354-9");
        assertThat(coding.getDisplay()).isEqualTo("Blood pressure panel");
    }

    @Test
    void conditionCodeIsSnomedCodeableConcept() {
        Condition condition = fhirService.readCondition("condition-001");
        Coding coding = fhirService.primaryCoding(condition.getCode());

        assertThat(coding.getSystem()).isEqualTo(SNOMED);
        assertThat(coding.getCode()).isEqualTo("38341003");
    }

    @Test
    void searchObservationsByCodeFindsResourcesNotValidatesTerminology() {
        Bundle bundle = fhirService.searchObservationsByCode("85354-9");

        assertThat(bundle.getType()).isEqualTo(Bundle.BundleType.SEARCHSET);
        assertThat(fhirService.resourceIdentities(bundle)).contains("Observation/obs-001");
    }

    @Test
    void searchConditionsByCodeFindsResourcesNotValidatesTerminology() {
        Bundle bundle = fhirService.searchConditionsByCode("38341003");

        assertThat(fhirService.resourceIdentities(bundle)).contains("Condition/condition-001");
    }

    @Test
    void validateLoincAgainstLocalHapiDoesNotHaveCodeSystem() {
        Parameters parameters = fhirService.validateCode(LOINC, "85354-9");

        assertThat(fhirService.validationResult(parameters)).isFalse();
        assertThat(fhirService.validationMessage(parameters)).isNotBlank();
    }

    @Test
    void validateInvalidLoincIsAlsoNotValidOnLocalHapi() {
        Parameters parameters = fhirService.validateCode(LOINC, "99999999");

        assertThat(fhirService.validationResult(parameters)).isFalse();
        assertThat(fhirService.validationMessage(parameters)).isNotBlank();
    }

    @Test
    void validateSnomedAgainstLocalHapiDoesNotHaveCodeSystem() {
        Parameters parameters = fhirService.validateCode(SNOMED, "38341003");

        assertThat(fhirService.validationResult(parameters)).isFalse();
        assertThat(fhirService.validationMessage(parameters)).isNotBlank();
    }

    @Test
    void validateInvalidSnomedIsNotValidOnLocalHapi() {
        Parameters parameters = fhirService.validateCode(SNOMED, "99999999");

        assertThat(fhirService.validationResult(parameters)).isFalse();
        assertThat(fhirService.validationMessage(parameters)).isNotBlank();
    }

    @Test
    void validateSyntheticLabCodeSystemDistinguishesValidAndInvalid() {
        Parameters valid = fhirService.validateCode(SyntheticTerminology.LAB_SYSTEM, SyntheticTerminology.LAB_CODE);
        Parameters invalid = fhirService.validateCode(SyntheticTerminology.LAB_SYSTEM, "99999999");

        assertThat(fhirService.validationResult(valid)).isTrue();
        assertThat(fhirService.validationResult(invalid)).isFalse();
    }

    @Test
    void localHapiHasNoExternalValueSets() {
        Bundle valueSets = fhirClient.search()
                .forResource("ValueSet")
                .count(5)
                .returnBundle(Bundle.class)
                .execute();

        assertThat(valueSets.getTotal()).isZero();
    }
}
