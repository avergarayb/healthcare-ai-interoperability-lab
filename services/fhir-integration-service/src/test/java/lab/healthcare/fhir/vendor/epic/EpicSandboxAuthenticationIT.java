package lab.healthcare.fhir.vendor.epic;

import lab.healthcare.fhir.client.FhirService;
import lab.healthcare.fhir.server.FhirServerProfile;
import lab.healthcare.fhir.smart.SmartAuthorizationCoordinator;
import lab.healthcare.fhir.vendor.FhirVendor;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE)
class EpicSandboxAuthenticationIT {

    @Autowired
    private EpicSandboxAuthenticationService epicSandboxAuthenticationService;

    @Autowired
    private EpicIntegrationProfile epicSandboxProfile;

    @Autowired
    private FhirServerProfile activeFhirServerProfile;

    @Autowired
    private FhirService fhirService;

    @Autowired
    private SmartAuthorizationCoordinator smartAuthorizationCoordinator;

    @Test
    void defaultDisabledEpicDoesNotStartAuthorization() {
        assertThat(activeFhirServerProfile.name()).isEqualTo("local-hapi");
        assertThat(activeFhirServerProfile.vendor()).isEqualTo(FhirVendor.GENERIC);
        assertThat(epicSandboxProfile.enabled()).isFalse();

        EpicSandboxAuthReadiness readiness = epicSandboxAuthenticationService.inspect(epicSandboxProfile);

        assertThat(readiness.state()).isEqualTo(EpicSandboxAuthReadinessState.DISABLED);
        assertThatThrownBy(() -> epicSandboxAuthenticationService.startAuthorization(epicSandboxProfile))
                .isInstanceOf(EpicProfileException.class)
                .hasMessageContaining("disabled")
                .hasMessageNotContaining("access_token");
        assertThat(readiness.toString()).doesNotContain("client_secret");
        assertThat(smartAuthorizationCoordinator).isNotNull();
        assertThat(fhirService).isNotNull();
    }
}
