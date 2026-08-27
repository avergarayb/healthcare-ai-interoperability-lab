package lab.healthcare.fhir.server;

import lab.healthcare.fhir.auth.FhirAuthenticationType;

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
        assertThat(properties.servers()).containsKeys("local-hapi", "example-org", "secured-lab", "smart-lab");
        assertThat(activeFhirServerProfile.name()).isEqualTo("local-hapi");
        assertThat(activeFhirServerProfile.baseUrl()).isEqualTo("http://localhost:8080/fhir");
        assertThat(activeFhirServerProfile.fhirVersion()).isEqualTo("R4");
        assertThat(activeFhirServerProfile.enabled()).isTrue();
        assertThat(activeFhirServerProfile.authentication().type()).isEqualTo(FhirAuthenticationType.NONE);
        assertThat(registry.profile("example-org").enabled()).isFalse();
        assertThat(registry.profile("secured-lab").enabled()).isFalse();
        assertThat(registry.profile("secured-lab").baseUrl()).isEqualTo("http://localhost:8180/fhir");
        assertThat(registry.profile("secured-lab").authentication().type())
                .isEqualTo(FhirAuthenticationType.OAUTH2_CLIENT_CREDENTIALS);
        assertThat(registry.profile("smart-lab").enabled()).isFalse();
        assertThat(registry.profile("smart-lab").authentication().type())
                .isEqualTo(FhirAuthenticationType.SMART_AUTHORIZATION_CODE);
        assertThat(fhirContext.getVersion().getVersion()).isEqualTo(FhirVersionEnum.R4);
        assertThat(fhirClient.getServerBase()).isEqualTo("http://localhost:8080/fhir");
    }
}
