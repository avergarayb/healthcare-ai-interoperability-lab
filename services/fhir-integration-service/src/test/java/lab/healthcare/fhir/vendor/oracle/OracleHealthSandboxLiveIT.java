package lab.healthcare.fhir.vendor.oracle;

import lab.healthcare.fhir.connectivity.FhirConnectivityStatus;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assumptions.assumeThat;

/**
 * Opt-in live check. Excluded from {@code -Pintegration}. Run with
 * {@code mvn verify -Poracle-live} and {@code ORACLE_HEALTH_LIVE_IT=true}.
 */
@EnabledIfEnvironmentVariable(named = "ORACLE_HEALTH_LIVE_IT", matches = "true")
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE)
class OracleHealthSandboxLiveIT {

    @Autowired
    private OracleSandboxReadinessService oracleSandboxReadinessService;

    @Autowired
    private OracleHealthIntegrationProfile oracleHealthSandboxProfile;

    @Test
    void configuredSandboxMetadataIsReachableWithoutReadingPatient() {
        assumeThat(oracleHealthSandboxProfile.enabled()).isTrue();
        assumeThat(oracleHealthSandboxProfile.fhirBaseUrl()).isNotBlank();

        OracleSandboxReadiness readiness = oracleSandboxReadinessService.inspect(oracleHealthSandboxProfile);
        assertThat(readiness.state()).isEqualTo(OracleSandboxReadinessState.READY_FOR_CONNECTIVITY_CHECK);

        FhirConnectivityStatus status = oracleSandboxReadinessService.checkConnectivity(oracleHealthSandboxProfile);
        assertThat(status.reachable()).isTrue();
        assertThat(status.toString()).doesNotContain("access_token");
        assertThat(status.toString()).doesNotContain("Patient/");
    }
}
