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
class FhirIncludeRevincludeIT {

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
    void searchObservationsByPatientDoesNotIncludePatientByDefault() {
        Bundle bundle = fhirService.searchObservationsByPatient("patient-001");

        assertThat(bundle.getType()).isEqualTo(Bundle.BundleType.SEARCHSET);
        assertThat(fhirService.resourceIdentities(bundle)).contains("Observation/obs-001");
        assertThat(fhirService.extractPatients(bundle)).isEmpty();
    }

    @Test
    void includeObservationSubjectReturnsObservationAndPatient() {
        Bundle bundle = fhirService.searchObservationsByPatientIncludingSubject("patient-001");

        assertThat(bundle.getType()).isEqualTo(Bundle.BundleType.SEARCHSET);
        assertThat(fhirService.resourceIdentities(bundle))
                .contains("Observation/obs-001", "Patient/patient-001");
    }

    @Test
    void revincludeObservationSubjectReturnsPatientAndObservation() {
        Bundle bundle = fhirService.searchPatientRevincludingObservationSubject("patient-001");

        assertThat(bundle.getType()).isEqualTo(Bundle.BundleType.SEARCHSET);
        assertThat(fhirService.resourceIdentities(bundle))
                .contains("Patient/patient-001", "Observation/obs-001");
    }

    @Test
    void revincludeConditionSubjectReturnsPatientAndCondition() {
        Bundle bundle = fhirService.searchPatientRevincludingConditionSubject("patient-001");

        assertThat(bundle.getType()).isEqualTo(Bundle.BundleType.SEARCHSET);
        assertThat(fhirService.resourceIdentities(bundle))
                .contains("Patient/patient-001", "Condition/condition-001");
    }

    @Test
    void combinedRevincludeReturnsPatientObservationAndCondition() {
        Bundle bundle = fhirService.searchPatientRevincludingObservationAndConditionSubject("patient-001");

        assertThat(bundle.getType()).isEqualTo(Bundle.BundleType.SEARCHSET);
        assertThat(fhirService.resourceIdentities(bundle))
                .contains("Patient/patient-001", "Observation/obs-001", "Condition/condition-001");
    }
}
