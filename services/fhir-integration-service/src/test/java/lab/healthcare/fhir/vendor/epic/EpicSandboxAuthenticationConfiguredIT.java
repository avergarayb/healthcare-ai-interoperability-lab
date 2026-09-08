package lab.healthcare.fhir.vendor.epic;

import lab.healthcare.fhir.server.FhirServerProfile;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest(
        webEnvironment = SpringBootTest.WebEnvironment.NONE,
        properties = {
            "fhir.active-server=local-hapi",
            "fhir.servers.epic-sandbox.enabled=true",
            "fhir.servers.epic-sandbox.authentication.client-id=lab-epic-placeholder",
            "fhir.servers.epic-sandbox.authentication.redirect-uri=http://127.0.0.1:8081/smart/callback",
            "fhir.servers.epic-sandbox.authentication.scope=user/Patient.read",
            "fhir.servers.epic-sandbox.authentication.smart-configuration-url="
                    + "http://127.0.0.1/does-not-contact-epic/.well-known/smart-configuration"
        })
class EpicSandboxAuthenticationConfiguredIT {

    @Autowired
    private EpicSandboxAuthenticationService epicSandboxAuthenticationService;

    @Autowired
    private EpicIntegrationProfile epicSandboxProfile;

    @Autowired
    private FhirServerProfile activeFhirServerProfile;

    @Test
    void enabledSyntheticSandboxIsReadyForAuthorizationWithoutCallingEpic() {
        assertThat(activeFhirServerProfile.name()).isEqualTo("local-hapi");
        assertThat(epicSandboxProfile.enabled()).isTrue();

        EpicSandboxAuthReadiness readiness = epicSandboxAuthenticationService.inspect(epicSandboxProfile);

        assertThat(readiness.state()).isEqualTo(EpicSandboxAuthReadinessState.READY_FOR_AUTHORIZATION);
        assertThat(readiness.toString()).doesNotContain("lab-epic-placeholder");
        assertThat(epicSandboxProfile.toString()).doesNotContain("client_secret");
    }
}
