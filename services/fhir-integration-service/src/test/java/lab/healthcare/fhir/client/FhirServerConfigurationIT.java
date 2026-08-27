package lab.healthcare.fhir.client;

import ca.uhn.fhir.rest.client.api.IGenericClient;
import org.hl7.fhir.r4.model.CapabilityStatement;
import org.hl7.fhir.r4.model.Enumerations;
import org.hl7.fhir.r4.model.Patient;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestInstance;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE)
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
class FhirServerConfigurationIT {

    @Autowired
    private FhirServerProfile activeFhirServerProfile;

    @Autowired
    private IGenericClient fhirClient;

    @Autowired
    private FhirService fhirService;

    @BeforeAll
    void seedSyntheticPatients() {
        SyntheticPatients.seed(fhirClient);
    }

    @Test
    void localHapiProfileReadsMetadataAndPatient() {
        assertThat(activeFhirServerProfile.name()).isEqualTo("local-hapi");
        assertThat(activeFhirServerProfile.baseUrl()).isEqualTo("http://localhost:8080/fhir");
        assertThat(fhirClient.getServerBase()).isEqualTo(activeFhirServerProfile.baseUrl());

        CapabilityStatement capabilityStatement = fhirService.retrieveCapabilityStatement();
        Patient patient = fhirService.readPatient("patient-001");

        assertThat(capabilityStatement.getFhirVersion()).isEqualTo(Enumerations.FHIRVersion._4_0_1);
        assertThat(patient.getIdElement().getIdPart()).isEqualTo("patient-001");
        assertThat(patient.getNameFirstRep().getFamily()).isEqualTo("Garcia");
    }
}
