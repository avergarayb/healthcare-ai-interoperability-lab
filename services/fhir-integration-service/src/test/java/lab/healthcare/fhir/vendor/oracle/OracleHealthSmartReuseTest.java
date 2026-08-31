package lab.healthcare.fhir.vendor.oracle;

import lab.healthcare.fhir.smart.Pkce;
import lab.healthcare.fhir.smart.SmartAuthorizationRequest;
import lab.healthcare.fhir.smart.SmartConfiguration;
import lab.healthcare.fhir.smart.SmartConfigurationValidator;
import lab.healthcare.fhir.smart.SmartFlowRequirements;

import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class OracleHealthSmartReuseTest {

    @Test
    void genericSmartComponentsConsumeOracleProfileWithoutCallingOracle() {
        OracleHealthIntegrationProfile profile = OracleHealthIntegrationProfileTest.completePublicPkce();
        SmartConfiguration discovered = new SmartConfiguration(
                "http://127.0.0.1/does-not-contact-oracle/authorize",
                "http://127.0.0.1/does-not-contact-oracle/token",
                List.of("patient/Patient.read"),
                List.of("code"),
                List.of("S256"),
                List.of());
        new SmartConfigurationValidator().validate(discovered, SmartFlowRequirements.authorizationCodePkceS256());

        SmartAuthorizationRequest request = SmartAuthorizationRequest.fromProfile(
                OracleHealthIntegrationProfileTest.smartAuth(),
                discovered,
                "lab-state",
                Pkce.codeChallengeS256("lab-pkce-verifier"));

        assertThat(request.aud()).isEqualTo(profile.aud());
        assertThat(request.scope()).isEqualTo(profile.requestedScopes());
        assertThat(request.codeChallengeMethod()).isEqualTo("S256");
        assertThat(request.toAuthorizationUrl())
                .startsWith("http://127.0.0.1/does-not-contact-oracle/authorize?");
    }
}
