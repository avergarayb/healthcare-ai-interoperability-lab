package lab.healthcare.fhir.client;

import ca.uhn.fhir.rest.client.api.IGenericClient;
import org.hl7.fhir.r4.model.Bundle;
import org.hl7.fhir.r4.model.Observation;
import org.hl7.fhir.r4.model.Patient;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestInstance;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import java.util.ArrayList;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE)
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
class FhirPaginationIT {

    @Autowired
    private FhirService fhirService;

    @Autowired
    private IGenericClient fhirClient;

    @BeforeAll
    void seedSyntheticResources() {
        SyntheticPatients.seed(fhirClient);
        SyntheticClinicalResources.seed(fhirClient);
        SyntheticPaginationPatients.seed(fhirClient);
    }

    @Test
    void firstPageIsSmallerThanTotalWhenCountIsLimited() {
        Bundle page = fhirService.searchPatientsByFamilyWithCount(SyntheticPaginationPatients.FAMILY, 3);

        assertThat(page.getType()).isEqualTo(Bundle.BundleType.SEARCHSET);
        assertThat(page.getTotal()).isGreaterThan(page.getEntry().size());
        assertThat(page.getTotal()).isGreaterThanOrEqualTo(SyntheticPaginationPatients.COUNT);
        assertThat(page.getEntry().size()).isLessThanOrEqualTo(3);
        assertThat(fhirService.hasNextPage(page)).isTrue();
        assertThat(fhirService.hasLink(page, Bundle.LINK_SELF)).isTrue();
        assertThat(fhirService.bundleLink(page, Bundle.LINK_NEXT)).isNotBlank();
    }

    @Test
    void nextPageUsesServerProvidedLinkAndDifferentEntries() {
        Bundle page1 = fhirService.searchPatientsByFamilyWithCount(SyntheticPaginationPatients.FAMILY, 3);
        String nextUrl = fhirService.bundleLink(page1, Bundle.LINK_NEXT);

        Bundle page2 = fhirService.nextPage(page1);

        assertThat(page2.getType()).isEqualTo(Bundle.BundleType.SEARCHSET);
        assertThat(nextUrl).contains("_getpages");
        assertThat(fhirService.hasLink(page2, Bundle.LINK_SELF)).isTrue();
        List<String> page1Ids = fhirService.resourceIdentities(page1);
        List<String> page2Ids = fhirService.resourceIdentities(page2);
        assertThat(page2Ids).isNotEmpty();
        assertThat(page2Ids).doesNotContainAnyElementsOf(page1Ids);
    }

    @Test
    void allPagesContainEverySyntheticPaginationPatientOnce() {
        Bundle first = fhirService.searchPatientsByFamilyWithCount(SyntheticPaginationPatients.FAMILY, 3);
        List<Bundle> pages = fhirService.fetchAllPages(first);

        List<String> ids = new ArrayList<>();
        for (Bundle page : pages) {
            ids.addAll(fhirService.extractPatients(page).stream()
                    .map(patient -> patient.getIdElement().getIdPart())
                    .toList());
        }

        assertThat(pages.getLast()).satisfies(last -> assertThat(fhirService.hasNextPage(last)).isFalse());
        assertThat(ids).doesNotHaveDuplicates();
        assertThat(ids).containsAll(SyntheticPaginationPatients.logicalIds());
        pages.forEach(page -> page.getEntry().stream()
                .map(Bundle.BundleEntryComponent::getResource)
                .filter(Patient.class::isInstance)
                .map(Patient.class::cast)
                .forEach(patient -> {
                    assertThat(patient.getIdElement().getIdPart()).isNotBlank();
                    assertThat(patient.getIdentifierFirstRep().getValue()).startsWith("MRN-PAG-");
                }));
    }

    @Test
    void familySearchPaginationStillReturnsASearchset() {
        Bundle page = fhirService.searchPatientsByFamilyWithCount(SyntheticPaginationPatients.FAMILY, 2);

        assertThat(page.getType()).isEqualTo(Bundle.BundleType.SEARCHSET);
        assertThat(page.getEntry().size()).isLessThanOrEqualTo(2);
        assertThat(page.getTotal()).isGreaterThan(page.getEntry().size());
        assertThat(fhirService.hasNextPage(page)).isTrue();
    }

    @Test
    void paginatedIncludeAddsIncludedResourcesToTheSameSearchset() {
        Bundle bundle = fhirClient.search()
                .forResource(Observation.class)
                .where(Observation.PATIENT.hasId("patient-001"))
                .include(Observation.INCLUDE_SUBJECT)
                .count(1)
                .returnBundle(Bundle.class)
                .execute();

        assertThat(bundle.getType()).isEqualTo(Bundle.BundleType.SEARCHSET);
        assertThat(fhirService.resourceIdentities(bundle)).contains("Observation/obs-001", "Patient/patient-001");
    }

    @Test
    void paginatedRevincludeCanMixPatientAndObservation() {
        Bundle bundle = fhirClient.search()
                .forResource(Patient.class)
                .where(Patient.RES_ID.exactly().code("patient-001"))
                .revInclude(Observation.INCLUDE_SUBJECT)
                .count(1)
                .returnBundle(Bundle.class)
                .execute();

        assertThat(bundle.getType()).isEqualTo(Bundle.BundleType.SEARCHSET);
        assertThat(fhirService.extractPatients(bundle)).extracting(patient -> patient.getIdElement().getIdPart())
                .contains("patient-001");
        assertThat(fhirService.resourceIdentities(bundle)).contains("Observation/obs-001");
    }
}
