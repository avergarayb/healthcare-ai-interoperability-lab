package lab.healthcare.fhir.vendor.oracle;

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
            "fhir.servers.oracle-health-sandbox.enabled=false",
            "fhir.servers.oracle-health-sandbox.base-url=http://127.0.0.1/oracle-health-sandbox",
            "fhir.servers.oracle-health-sandbox.authentication.client-id=lab-oracle-placeholder",
            "fhir.servers.oracle-health-sandbox.authentication.redirect-uri=http://127.0.0.1:8081/smart/callback",
            "fhir.servers.oracle-health-sandbox.authentication.scope=patient/Patient.read",
            "fhir.servers.oracle-health-sandbox.authentication.aud=http://127.0.0.1/oracle-health-sandbox",
            "fhir.servers.oracle-health-sandbox.authentication.smart-configuration-url="
                    + "http://127.0.0.1/does-not-contact-oracle/.well-known/smart-configuration"
        })
class OracleHealthIntegrationProfileConfiguredIT {

    @Autowired
    private OracleHealthIntegrationProfile oracleHealthSandboxProfile;

    @Autowired
    private FhirServerProfile activeFhirServerProfile;

    @Autowired
    private OracleHealthProfileValidator oracleHealthProfileValidator;

    @Test
    void syntheticConfigurationIsReadyForSandboxWithoutContactingOracle() {
        assertThat(activeFhirServerProfile.name()).isEqualTo("local-hapi");
        assertThat(oracleHealthSandboxProfile.enabled()).isFalse();
        assertThat(oracleHealthSandboxProfile.readiness()).isEqualTo(OracleHealthReadinessState.READY_FOR_SANDBOX);
        oracleHealthProfileValidator.validateForRuntime(oracleHealthSandboxProfile);

        SmartConfiguration discovered = new SmartConfiguration(
                "http://127.0.0.1/does-not-contact-oracle/authorize",
                "http://127.0.0.1/does-not-contact-oracle/token",
                List.of("patient/Patient.read"),
                List.of("code"),
                List.of("S256"),
                List.of());
        new SmartConfigurationValidator().validate(discovered);
        SmartAuthorizationRequest request = SmartAuthorizationRequest.fromProfile(
                oracleHealthSandboxProfile.toAuthenticationSettings(),
                discovered,
                "lab-state",
                Pkce.codeChallengeS256("lab-pkce-verifier"));

        assertThat(request.aud()).isEqualTo("http://127.0.0.1/oracle-health-sandbox");
        assertThat(request.clientId()).isEqualTo("lab-oracle-placeholder");
        assertThat(oracleHealthSandboxProfile.smartConfigurationUrl()).startsWith("http://127.0.0.1/");
        assertThat(request.toAuthorizationUrl()).contains("http://127.0.0.1/does-not-contact-oracle/authorize");
    }
}
