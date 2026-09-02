package lab.healthcare.fhir.vendor.oracle;

import lab.healthcare.fhir.smart.SmartAuthorizationStart;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assumptions.assumeThat;

/**
 * Opt-in live SMART discovery + authorization URL. Excluded from {@code -Pintegration}.
 * Browser login is manual; token exchange against Oracle is not automated here.
 * Run with {@code mvn verify -Poracle-live} and {@code ORACLE_HEALTH_LIVE_IT=true}.
 */
@EnabledIfEnvironmentVariable(named = "ORACLE_HEALTH_LIVE_IT", matches = "true")
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE)
class OracleHealthSandboxAuthLiveIT {

    @Autowired
    private OracleSandboxAuthenticationService oracleSandboxAuthenticationService;

    @Autowired
    private OracleHealthIntegrationProfile oracleHealthSandboxProfile;

    @Test
    void configuredSandboxDiscoversSmartAndBuildsAuthorizationUrl() {
        assumeThat(oracleHealthSandboxProfile.enabled()).isTrue();
        assumeThat(oracleHealthSandboxProfile.smartConfigurationUrl()).isNotBlank();

        OracleSandboxAuthReadiness readiness =
                oracleSandboxAuthenticationService.inspect(oracleHealthSandboxProfile);
        assertThat(readiness.state()).isEqualTo(OracleSandboxAuthReadinessState.READY_FOR_AUTHORIZATION);

        SmartAuthorizationStart start =
                oracleSandboxAuthenticationService.startAuthorization(oracleHealthSandboxProfile);

        assertThat(start.authorizationUrl()).contains("response_type=code");
        assertThat(start.authorizationUrl()).contains("code_challenge_method=S256");
        assertThat(start.authorizationUrl()).contains("aud=");
        assertThat(start.state()).isNotBlank();
        assertThat(start.toString()).doesNotContain("access_token");
        assertThat(start.toString()).doesNotContain("code_verifier");
    }
}
