package lab.healthcare.fhir.client;

import ca.uhn.fhir.context.FhirContext;
import ca.uhn.fhir.context.FhirVersionEnum;
import ca.uhn.fhir.rest.client.api.IGenericClient;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE)
class FhirServersPropertiesTest {

    @Autowired
    private FhirServersProperties properties;

    @Autowired
    private FhirServerProfile activeFhirServerProfile;

    @Autowired
    private FhirServerProfileRegistry registry;

    @Autowired
    private FhirContext fhirContext;

    @Autowired
    private IGenericClient fhirClient;

    @Test
    void applicationYamlBindsLocalHapiAsActiveProfile() {
        assertThat(properties.activeServer()).isEqualTo("local-hapi");
        assertThat(properties.servers()).containsKeys("local-hapi", "example-org");
        assertThat(activeFhirServerProfile.name()).isEqualTo("local-hapi");
        assertThat(activeFhirServerProfile.baseUrl()).isEqualTo("http://localhost:8080/fhir");
        assertThat(activeFhirServerProfile.fhirVersion()).isEqualTo("R4");
        assertThat(activeFhirServerProfile.enabled()).isTrue();
        assertThat(registry.profile("example-org").enabled()).isFalse();
        assertThat(fhirContext.getVersion().getVersion()).isEqualTo(FhirVersionEnum.R4);
        assertThat(fhirClient.getServerBase()).isEqualTo("http://localhost:8080/fhir");
    }
}
