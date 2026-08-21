package lab.healthcare.fhir.client;

import ca.uhn.fhir.rest.client.api.IGenericClient;
import org.hl7.fhir.r4.model.Bundle;
import org.hl7.fhir.r4.model.Patient;
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
class FhirPatientSearchIT {

    @Autowired
    private FhirService fhirService;

    @Autowired
    private IGenericClient fhirClient;

    @BeforeAll
    void seedSyntheticPatients() {
        SyntheticPatients.seed(fhirClient);
    }

    @Test
    void readPatientByLogicalId() {
        Patient patient = fhirService.readPatient("patient-001");

        assertThat(patient.getIdElement().getIdPart()).isEqualTo("patient-001");
        assertThat(patient.getNameFirstRep().getFamily()).isEqualTo("Garcia");
        assertThat(patient.getNameFirstRep().getGivenAsSingleString()).isEqualTo("Maria");
        assertThat(patient.getIdentifierFirstRep().getValue()).isEqualTo("MRN-10001");
    }

    @Test
    void searchPatientsByNameReturnsMatchingBundle() {
        Bundle bundle = fhirService.searchPatientsByName("Maria");

        assertThat(bundle.getType()).isEqualTo(Bundle.BundleType.SEARCHSET);
        Set<String> ids = fhirService.extractPatients(bundle).stream()
                .map(patient -> patient.getIdElement().getIdPart())
                .collect(Collectors.toSet());
        Set<String> names = fhirService.extractPatients(bundle).stream()
                .map(patient -> patient.getNameFirstRep().getGivenAsSingleString() + " " + patient.getNameFirstRep().getFamily())
                .collect(Collectors.toSet());

        assertThat(ids).containsExactlyInAnyOrder("patient-001", "patient-003");
        assertThat(names).containsExactlyInAnyOrder("Maria Garcia", "Maria Lopez");
        assertThat(ids).doesNotContain("patient-002");
    }

    @Test
    void searchPatientsByIdentifierReturnsSinglePatient() {
        Bundle bundle = fhirService.searchPatientsByIdentifier("MRN-10001");

        assertThat(bundle.getType()).isEqualTo(Bundle.BundleType.SEARCHSET);
        assertThat(fhirService.extractPatients(bundle))
                .extracting(patient -> patient.getIdElement().getIdPart())
                .containsExactly("patient-001");
    }
}
