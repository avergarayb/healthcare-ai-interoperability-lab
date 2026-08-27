package lab.healthcare.fhir.client;

import lab.healthcare.fhir.exception.FhirClientException;

import ca.uhn.fhir.rest.client.api.IGenericClient;
import ca.uhn.fhir.rest.server.exceptions.BaseServerResponseException;
import ca.uhn.fhir.rest.server.exceptions.ResourceNotFoundException;
import org.hl7.fhir.r4.model.Bundle;
import org.hl7.fhir.r4.model.Resource;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestInstance;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE)
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
class FhirEverythingIT {

    @Autowired
    private FhirService fhirService;

    @Autowired
    private IGenericClient fhirClient;

    @BeforeAll
    void seedSyntheticResources() {
        SyntheticPatients.seed(fhirClient);
        SyntheticClinicalResources.seed(fhirClient);
        SyntheticEverythingResources.seed(fhirClient);
    }

    @Test
    void patientEverythingReturnsSearchsetWithPatientAndRelatedResources() {
        Bundle bundle = fhirService.getPatientEverything(SyntheticEverythingResources.PATIENT_ID);

        assertThat(bundle.getType()).isEqualTo(Bundle.BundleType.SEARCHSET);
        assertThat(bundle.getEntry()).isNotEmpty();
        assertThat(fhirService.resourceIdentities(bundle)).contains(
                "Patient/patient-001",
                "Observation/obs-001",
                "Condition/condition-001",
                "Encounter/encounter-001",
                "MedicationRequest/medreq-001",
                "Observation/everything-obs-dated");
        assertThat(bundle.getEntry())
                .allMatch(entry -> entry.hasSearch() && entry.getSearch().hasMode());
    }

    @Test
    void patientEverythingByObservationTypeOmitsPatient() {
        Bundle bundle = fhirService.getPatientEverythingByTypes(
                SyntheticEverythingResources.PATIENT_ID, "Observation");

        assertThat(bundle.getType()).isEqualTo(Bundle.BundleType.SEARCHSET);
        assertThat(fhirService.resourceIdentities(bundle)).contains("Observation/obs-001");
        assertThat(resourceTypes(bundle)).containsOnly("Observation");
        assertThat(fhirService.resourceIdentities(bundle)).doesNotContain("Patient/patient-001");
    }

    @Test
    void patientEverythingByObservationAndConditionTypes() {
        Bundle bundle = fhirService.getPatientEverythingByTypes(
                SyntheticEverythingResources.PATIENT_ID, "Observation", "Condition");

        assertThat(resourceTypes(bundle)).containsExactlyInAnyOrder("Observation", "Condition");
        assertThat(fhirService.resourceIdentities(bundle))
                .contains("Observation/obs-001", "Condition/condition-001")
                .doesNotContain("Patient/patient-001", "Encounter/encounter-001");
    }

    @Test
    void patientEverythingPaginatesWithCountAndReusesNextPage() {
        Bundle page1 = fhirService.getPatientEverything(SyntheticEverythingResources.PATIENT_ID, 2);

        assertThat(page1.getType()).isEqualTo(Bundle.BundleType.SEARCHSET);
        assertThat(page1.getEntry()).hasSize(2);
        assertThat(page1.getTotal()).isGreaterThan(2);
        assertThat(fhirService.hasNextPage(page1)).isTrue();
        assertThat(fhirService.bundleLink(page1, Bundle.LINK_NEXT)).contains("_getpages");

        Bundle page2 = fhirService.nextPage(page1);
        assertThat(page2.getType()).isEqualTo(Bundle.BundleType.SEARCHSET);
        assertThat(page2.getEntry()).isNotEmpty();
        assertThat(fhirService.resourceIdentities(page2))
                .doesNotContainAnyElementsOf(fhirService.resourceIdentities(page1));
    }

    @Test
    void patientEverythingDoesNotSwallowMissingPatient() {
        assertThatThrownBy(() -> fhirService.getPatientEverything("does-not-exist"))
                .isInstanceOf(FhirClientException.class)
                .cause()
                .isInstanceOf(ResourceNotFoundException.class)
                .extracting(cause -> ((BaseServerResponseException) cause).getStatusCode())
                .isEqualTo(404);
    }

    @Test
    void everythingIsNotTheSameAsIncludeOrRevinclude() {
        Bundle everything = fhirService.getPatientEverything(SyntheticEverythingResources.PATIENT_ID);
        Bundle included = fhirService.searchObservationsByPatientIncludingSubject("patient-001");
        Bundle revincluded = fhirService.searchPatientRevincludingObservationAndConditionSubject("patient-001");

        assertThat(everything.getType()).isEqualTo(Bundle.BundleType.SEARCHSET);
        assertThat(included.getType()).isEqualTo(Bundle.BundleType.SEARCHSET);
        assertThat(revincluded.getType()).isEqualTo(Bundle.BundleType.SEARCHSET);
        assertThat(fhirService.resourceIdentities(everything))
                .contains("Encounter/encounter-001", "MedicationRequest/medreq-001");
        assertThat(fhirService.resourceIdentities(included)).contains("Observation/obs-001", "Patient/patient-001");
        assertThat(fhirService.resourceIdentities(included)).doesNotContain("Encounter/encounter-001");
        assertThat(fhirService.resourceIdentities(revincluded))
                .contains("Patient/patient-001", "Observation/obs-001", "Condition/condition-001");
        assertThat(searchModes(included)).contains("match", "include");
        assertThat(searchModes(everything)).containsOnly("match");
    }

    private static Set<String> resourceTypes(Bundle bundle) {
        return bundle.getEntry().stream()
                .map(Bundle.BundleEntryComponent::getResource)
                .map(Resource::fhirType)
                .collect(Collectors.toSet());
    }

    private static List<String> searchModes(Bundle bundle) {
        return bundle.getEntry().stream()
                .map(entry -> entry.getSearch().getMode().toCode())
                .distinct()
                .toList();
    }
}
