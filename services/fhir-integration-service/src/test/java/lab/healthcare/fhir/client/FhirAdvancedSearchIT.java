package lab.healthcare.fhir.client;

import ca.uhn.fhir.rest.client.api.IGenericClient;
import org.hl7.fhir.r4.model.Bundle;
import org.hl7.fhir.r4.model.Patient;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestInstance;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE)
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
class FhirAdvancedSearchIT {

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
    void searchPatientsByNameAndGenderUsesAndSemantics() {
        Bundle bundle = fhirService.searchPatientsByNameAndGender("Maria", "female");

        assertThat(bundle.getType()).isEqualTo(Bundle.BundleType.SEARCHSET);
        List<String> ids = patientIds(bundle);
        assertThat(ids).contains("patient-001", "patient-003");
        assertThat(ids).doesNotContain("patient-002");
    }

    @Test
    void searchObservationsByPatientAndCodeReturnsSeededObservation() {
        Bundle bundle = fhirService.searchObservationsByPatientAndCode("patient-001", "85354-9");

        assertThat(bundle.getType()).isEqualTo(Bundle.BundleType.SEARCHSET);
        assertThat(fhirService.extractObservations(bundle))
                .extracting(observation -> observation.getIdElement().getIdPart())
                .contains("obs-001");
    }

    @Test
    void searchConditionsByPatientAndClinicalStatusReturnsSeededCondition() {
        Bundle bundle = fhirService.searchConditionsByPatientAndClinicalStatus("patient-001", "active");

        assertThat(bundle.getType()).isEqualTo(Bundle.BundleType.SEARCHSET);
        assertThat(fhirService.extractConditions(bundle))
                .extracting(condition -> condition.getIdElement().getIdPart())
                .contains("condition-001");
    }

    @Test
    void nameExactMariaMatchesGivenName() {
        Bundle bundle = fhirService.searchPatientsByNameExact("Maria");

        assertThat(patientIds(bundle)).contains("patient-001", "patient-003");
        assertThat(patientIds(bundle)).doesNotContain("patient-002");
    }

    @Test
    void nameExactModifierIsStricterThanDefaultNameSearch() {
        List<String> prefixIds = patientIds(fhirService.searchPatientsByName("Gar"));
        List<String> exactIds = patientIds(fhirService.searchPatientsByNameExact("Gar"));

        assertThat(prefixIds).contains("patient-001", "patient-002");
        assertThat(exactIds).doesNotContain("patient-001", "patient-002", "patient-003");
    }

    @Test
    void searchPatientsBornOnOrAfterIncludesMariaGarciaAndMariaLopez() {
        Bundle bundle = fhirService.searchPatientsBornOnOrAfter("1985-01-01");

        List<String> ids = patientIds(bundle);
        assertThat(ids).contains("patient-001", "patient-003");
        assertThat(ids).doesNotContain("patient-002");
    }

    @Test
    void searchPatientsBornBeforeExcludesMariaLopez() {
        Bundle bundle = fhirService.searchPatientsBornBefore("1990-01-01");

        List<String> ids = patientIds(bundle);
        assertThat(ids).contains("patient-001", "patient-002");
        assertThat(ids).doesNotContain("patient-003");
    }

    @Test
    void sortByBirthDateAscendingOrdersTheSeededPatients() {
        List<String> ids = allPatientIds(fhirService.searchPatientsSortedByBirthDateAscending());

        assertThat(ids).contains("patient-001", "patient-002", "patient-003");
        assertThat(ids.indexOf("patient-002")).isLessThan(ids.indexOf("patient-001"));
        assertThat(ids.indexOf("patient-001")).isLessThan(ids.indexOf("patient-003"));
    }

    @Test
    void sortByBirthDateDescendingReversesTheSeededPatients() {
        List<String> ids = allPatientIds(fhirService.searchPatientsSortedByBirthDateDescending());

        assertThat(ids).contains("patient-001", "patient-002", "patient-003");
        assertThat(ids.indexOf("patient-003")).isLessThan(ids.indexOf("patient-001"));
        assertThat(ids.indexOf("patient-001")).isLessThan(ids.indexOf("patient-002"));
    }

    @Test
    void countRequestsPageSizeNotTotalMatches() {
        Bundle bundle = fhirService.searchPatientsWithCount(2);

        assertThat(bundle.getType()).isEqualTo(Bundle.BundleType.SEARCHSET);
        assertThat(bundle.getEntry()).hasSize(2);
        assertThat(bundle.getLink(Bundle.LINK_SELF)).isNotNull();
        assertThat(bundle.getLink(Bundle.LINK_NEXT)).isNotNull();
        if (bundle.hasTotal()) {
            assertThat(bundle.getTotal()).isGreaterThan(bundle.getEntry().size());
        }
    }

    @Test
    void combinedObservationSearchKeepsPatientCodeSortAndCount() {
        Bundle bundle = fhirService.searchObservationsByPatientAndCodeSortedByDate("patient-001", "85354-9", 10);

        assertThat(bundle.getType()).isEqualTo(Bundle.BundleType.SEARCHSET);
        assertThat(bundle.getEntry()).hasSizeLessThanOrEqualTo(10);
        assertThat(fhirService.extractObservations(bundle))
                .extracting(observation -> observation.getIdElement().getIdPart())
                .contains("obs-001");
    }

    private List<String> patientIds(Bundle bundle) {
        return fhirService.extractPatients(bundle).stream()
                .map(Patient::getIdElement)
                .map(id -> id.getIdPart())
                .toList();
    }

    private List<String> allPatientIds(Bundle firstPage) {
        return fhirService.fetchAllPages(firstPage).stream()
                .flatMap(page -> patientIds(page).stream())
                .toList();
    }
}
