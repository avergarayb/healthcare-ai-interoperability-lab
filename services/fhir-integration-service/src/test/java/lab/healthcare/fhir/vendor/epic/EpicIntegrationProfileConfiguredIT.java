package lab.healthcare.fhir.vendor.epic;

import lab.healthcare.fhir.server.FhirServerProfile;
import lab.healthcare.fhir.smart.Pkce;
import lab.healthcare.fhir.smart.SmartAuthorizationRequest;
import lab.healthcare.fhir.smart.SmartConfiguration;
import lab.healthcare.fhir.smart.SmartConfigurationValidator;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest(
        webEnvironment = SpringBootTest.WebEnvironment.NONE,
        properties = {
            "fhir.active-server=local-hapi",
            "fhir.servers.epic-sandbox.enabled=false",
            "fhir.servers.epic-sandbox.authentication.client-id=lab-epic-placeholder",
            "fhir.servers.epic-sandbox.authentication.redirect-uri=http://127.0.0.1:8081/smart/callback",
            "fhir.servers.epic-sandbox.authentication.scope=patient/Patient.read",
            "fhir.servers.epic-sandbox.authentication.smart-configuration-url="
                    + "http://127.0.0.1/does-not-contact-epic/.well-known/smart-configuration"
        })
class EpicIntegrationProfileConfiguredIT {

    @Autowired
    private EpicIntegrationProfile epicSandboxProfile;

    @Autowired
    private FhirServerProfile activeFhirServerProfile;

    @Autowired
    private EpicProfileValidator epicProfileValidator;

    @Test
    void syntheticConfigurationIsReadyForSandboxWithoutContactingEpic() {
        assertThat(activeFhirServerProfile.name()).isEqualTo("local-hapi");
        assertThat(epicSandboxProfile.enabled()).isFalse();
        assertThat(epicSandboxProfile.readiness()).isEqualTo(EpicReadinessState.READY_FOR_SANDBOX);
        epicProfileValidator.validateForRuntime(epicSandboxProfile);

        SmartConfiguration discovered = new SmartConfiguration(
                "http://127.0.0.1/does-not-contact-epic/authorize",
                "http://127.0.0.1/does-not-contact-epic/token",
                List.of("patient/Patient.read"),
                List.of("code"),
                List.of("S256"),
                List.of());
        new SmartConfigurationValidator().validate(discovered);
        SmartAuthorizationRequest request = SmartAuthorizationRequest.fromProfile(
                epicSandboxProfile.toAuthenticationSettings(),
                discovered,
                "lab-state",
                Pkce.codeChallengeS256("lab-pkce-verifier"));

        assertThat(request.aud()).isEqualTo(epicSandboxProfile.aud());
        assertThat(request.clientId()).isEqualTo("lab-epic-placeholder");
        assertThat(epicSandboxProfile.smartConfigurationUrl()).startsWith("http://127.0.0.1/");
        assertThat(request.toAuthorizationUrl()).contains("http://127.0.0.1/does-not-contact-epic/authorize");
    }
}
