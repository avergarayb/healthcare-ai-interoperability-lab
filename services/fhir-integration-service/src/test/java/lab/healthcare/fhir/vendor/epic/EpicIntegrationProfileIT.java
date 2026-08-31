package lab.healthcare.fhir.vendor.epic;

import lab.healthcare.fhir.client.FhirService;
import lab.healthcare.fhir.server.FhirServerProfile;
import lab.healthcare.fhir.server.FhirServerProfileRegistry;
import lab.healthcare.fhir.vendor.FhirVendor;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE)
class EpicIntegrationProfileIT {

    @Autowired
    private EpicIntegrationProfile epicSandboxProfile;

    @Autowired
    private FhirServerProfile activeFhirServerProfile;

    @Autowired
    private FhirServerProfileRegistry registry;

    @Autowired
    private FhirService fhirService;

    @Autowired
    private EpicProfileValidator epicProfileValidator;

    @Test
    void defaultYamlBindsDisabledEpicSandboxWithoutCredentials() {
        assertThat(activeFhirServerProfile.name()).isEqualTo("local-hapi");
        assertThat(activeFhirServerProfile.vendor()).isEqualTo(FhirVendor.GENERIC);
        assertThat(registry.profile("epic-sandbox").enabled()).isFalse();
        assertThat(epicSandboxProfile.vendor()).isEqualTo(FhirVendor.EPIC);
        assertThat(epicSandboxProfile.enabled()).isFalse();
        assertThat(epicSandboxProfile.environment()).isEqualTo(EpicEnvironment.SANDBOX);
        assertThat(epicSandboxProfile.fhirBaseUrl()).isEqualTo(EpicSandboxEndpoints.FHIR_R4_BASE);
        assertThat(epicSandboxProfile.aud()).isEqualTo(EpicSandboxEndpoints.FHIR_R4_BASE);
        assertThat(epicSandboxProfile.clientId()).isEmpty();
        assertThat(epicSandboxProfile.smartConfigurationUrl()).isEmpty();
        assertThat(epicSandboxProfile.readiness()).isEqualTo(EpicReadinessState.NOT_CONFIGURED);
        assertThat(epicSandboxProfile.clientAuthentication()).isEqualTo(EpicClientAuthentication.PUBLIC_PKCE);
        assertThatCode(() -> epicProfileValidator.validate(epicSandboxProfile)).doesNotThrowAnyException();
        assertThat(fhirService).isNotNull();
        assertThat(epicSandboxProfile.toString()).doesNotContain("client_secret");
    }
}
