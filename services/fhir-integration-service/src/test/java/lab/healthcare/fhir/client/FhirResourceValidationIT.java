package lab.healthcare.fhir.client;

import ca.uhn.fhir.rest.api.MethodOutcome;
import ca.uhn.fhir.rest.client.api.IGenericClient;
import org.hl7.fhir.r4.model.CodeableConcept;
import org.hl7.fhir.r4.model.Coding;
import org.hl7.fhir.r4.model.Observation;
import org.hl7.fhir.r4.model.OperationOutcome;
import org.hl7.fhir.r4.model.Quantity;
import org.hl7.fhir.r4.model.Reference;
import org.hl7.fhir.r4.model.StructureDefinition;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestInstance;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE)
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
class FhirResourceValidationIT {

    @Autowired
    private FhirService fhirService;

    @Autowired
    private IGenericClient fhirClient;

    @BeforeAll
    void seedSyntheticResources() {
        SyntheticPatients.seed(fhirClient);
        SyntheticClinicalResources.seed(fhirClient);
        SyntheticProfiles.seed(fhirClient);
    }

    @Test
    void storedProfileIsAConstraintOnObservation() {
        StructureDefinition profile = fhirClient.read()
                .resource(StructureDefinition.class)
                .withId(SyntheticProfiles.LAB_BP_PROFILE_ID)
                .execute();

        assertThat(profile.getUrl()).isEqualTo(SyntheticProfiles.LAB_BP_PROFILE_URL);
        assertThat(profile.getType()).isEqualTo("Observation");
        assertThat(profile.getBaseDefinition()).isEqualTo("http://hl7.org/fhir/StructureDefinition/Observation");
        assertThat(profile.getDerivation()).isEqualTo(StructureDefinition.TypeDerivationRule.CONSTRAINT);
        assertThat(profile.hasDifferential()).isTrue();
        assertThat(profile.getDifferential().getElement()).anyMatch(element ->
                "Observation.subject".equals(element.getPath()) && element.getMin() == 1);
    }

    @Test
    void baseValidationOfObs001HasNoErrorIssues() {
        Observation observation = fhirService.readObservation("obs-001");
        OperationOutcome outcome = fhirService.operationOutcome(fhirService.validateResource(observation));

        assertThat(fhirService.hasErrorIssue(outcome)).isFalse();
        assertThat(fhirService.issueDiagnostics(outcome)).isNotEmpty();
    }

    @Test
    void baseValidationOfIncompleteObservationReportsRequiredElements() {
        Observation invalid = new Observation();
        invalid.setId("invalid-observation");
        OperationOutcome outcome = fhirService.operationOutcome(fhirService.validateResource(invalid));

        assertThat(fhirService.hasErrorIssue(outcome)).isTrue();
        assertThat(fhirService.issueDiagnostics(outcome)).anyMatch(diagnostics ->
                diagnostics.contains("Observation.status") && diagnostics.contains("minimum required = 1"));
        assertThat(fhirService.issueDiagnostics(outcome)).anyMatch(diagnostics ->
                diagnostics.contains("Observation.code") && diagnostics.contains("minimum required = 1"));
    }

    @Test
    void profileValidationSucceedsForObservationWithSubjectAndValue() {
        Observation observation = fhirService.readObservation("obs-001");
        OperationOutcome outcome = fhirService.operationOutcome(
                fhirService.validateResourceAgainstProfile(observation, SyntheticProfiles.LAB_BP_PROFILE_URL));

        assertThat(fhirService.hasErrorIssue(outcome)).isFalse();
    }

    @Test
    void profileMakesMissingSubjectAnError() {
        Observation withoutSubject = bloodPressureWithoutSubject();
        OperationOutcome base = fhirService.operationOutcome(fhirService.validateResource(withoutSubject));
        OperationOutcome profiled = fhirService.operationOutcome(
                fhirService.validateResourceAgainstProfile(withoutSubject, SyntheticProfiles.LAB_BP_PROFILE_URL));

        assertThat(fhirService.hasErrorIssue(base)).isFalse();
        assertThat(fhirService.hasErrorIssue(profiled)).isTrue();
        assertThat(fhirService.issueDiagnostics(profiled)).anyMatch(diagnostics ->
                diagnostics.contains("Observation.subject")
                        && diagnostics.contains(SyntheticProfiles.LAB_BP_PROFILE_URL));
    }

    @Test
    void metaProfileIsADeclarationNotProofOfConformance() {
        Observation declaredButInvalid = bloodPressureWithoutSubject();
        declaredButInvalid.getMeta().addProfile(SyntheticProfiles.LAB_BP_PROFILE_URL);

        assertThat(fhirService.declaredProfiles(declaredButInvalid))
                .containsExactly(SyntheticProfiles.LAB_BP_PROFILE_URL);

        OperationOutcome outcome = fhirService.operationOutcome(fhirService.validateResource(declaredButInvalid));

        assertThat(fhirService.hasErrorIssue(outcome)).isTrue();
        assertThat(fhirService.issueDiagnostics(outcome)).anyMatch(diagnostics ->
                diagnostics.contains(SyntheticProfiles.LAB_BP_PROFILE_URL));
    }

    @Test
    void validateCodeReturnsParametersWhileValidateReturnsOperationOutcome() {
        Observation observation = fhirService.readObservation("obs-001");
        MethodOutcome resourceValidation = fhirService.validateResource(observation);

        assertThat(fhirService.validateCode("http://loinc.org", "85354-9").getParameter("result")).isNotNull();
        assertThat(fhirService.operationOutcome(resourceValidation).getIssue()).isNotEmpty();
    }

    private static Observation bloodPressureWithoutSubject() {
        Observation observation = new Observation();
        observation.setStatus(Observation.ObservationStatus.FINAL);
        observation.setCode(new CodeableConcept().addCoding(new Coding()
                .setSystem("http://loinc.org")
                .setCode("85354-9")
                .setDisplay("Blood pressure panel")));
        observation.setValue(new Quantity()
                .setValue(130)
                .setUnit("mmHg")
                .setSystem("http://unitsofmeasure.org")
                .setCode("mm[Hg]"));
        return observation;
    }
}
