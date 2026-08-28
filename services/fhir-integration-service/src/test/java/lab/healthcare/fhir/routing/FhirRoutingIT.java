package lab.healthcare.fhir.routing;

import lab.healthcare.fhir.client.FhirService;
import lab.healthcare.fhir.client.SyntheticPatients;
import lab.healthcare.fhir.mapping.LabMappingDefinitions;
import lab.healthcare.fhir.mapping.MappingService;
import lab.healthcare.fhir.server.FhirServerProfile;

import ca.uhn.fhir.rest.client.api.IGenericClient;
import org.hl7.fhir.r4.model.Patient;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestInstance;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE)
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
class FhirRoutingIT {

    @Autowired
    private RoutingService routingService;

    @Autowired
    private FhirService fhirService;

    @Autowired
    private MappingService mappingService;

    @Autowired
    private IGenericClient fhirClient;

    @BeforeAll
    void seedSyntheticPatients() {
        SyntheticPatients.seed(fhirClient);
    }

    @Test
    void routesPatientReadToLocalHapi() {
        RoutingRequest request = RoutingRequest.readPatient("local-hapi", "patient-001");

        FhirServerProfile profile = routingService.resolve(request);
        Patient patient = routingService.readPatient(request);

        assertThat(profile.name()).isEqualTo("local-hapi");
        assertThat(profile.baseUrl()).isEqualTo("http://localhost:8080/fhir");
        assertThat(routingService.client(request).getServerBase()).isEqualTo("http://localhost:8080/fhir");
        assertThat(patient.getIdElement().getIdPart()).isEqualTo("patient-001");
        assertThat(patient.getNameFirstRep().getFamily()).isEqualTo("Garcia");
        assertThat(patient.getNameFirstRep().getGivenAsSingleString()).isEqualTo("Maria");
        assertThat(fhirService.readPatient("patient-001").getIdElement().getIdPart()).isEqualTo("patient-001");
    }

    @Test
    void unknownDestinationDoesNotFallBackToLocalHapi() {
        assertThatThrownBy(() -> routingService.readPatient(RoutingRequest.readPatient("does-not-exist", "patient-001")))
                .isInstanceOf(RoutingException.class)
                .hasMessageContaining("does-not-exist");
    }

    @Test
    void disabledExampleOrgDoesNotFallBackToLocalHapi() {
        assertThatThrownBy(() -> routingService.readPatient(RoutingRequest.readPatient("example-org", "patient-001")))
                .isInstanceOf(RoutingException.class)
                .hasMessageContaining("example-org")
                .hasMessageContaining("disabled");
    }

    @Test
    void mappingRemainsIndependentOfRouting() {
        Patient mapped = mappingService.mapPatient(
                """
                {
                  "patient_id": "MAP-020-001",
                  "first_name": "John",
                  "last_name": "Smith",
                  "date_of_birth": "1980-05-20"
                }
                """,
                LabMappingDefinitions.patient());

        assertThat(mapped.getIdentifierFirstRep().getValue()).isEqualTo("MAP-020-001");
        FhirServerProfile profile = routingService.resolve(RoutingRequest.readPatient("local-hapi", "patient-001"));
        assertThat(profile.name()).isEqualTo("local-hapi");
        assertThat(mapped.getIdElement().getIdPart()).isNull();
    }
}
