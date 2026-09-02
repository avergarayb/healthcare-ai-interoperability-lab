package lab.healthcare.fhir.vendor.oracle;

import lab.healthcare.fhir.routing.FhirAuthenticatedReadOutcome;
import lab.healthcare.fhir.routing.FhirAuthenticatedReadResult;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assumptions.assumeThat;

/**
 * Opt-in authenticated Patient SEARCH_TYPE. Excluded from {@code -Pintegration}.
 * Maven cannot complete browser login, so a missing session token is
 * {@code AUTHENTICATION_REQUIRED}. Do not fabricate credentials.
 * Run with {@code mvn verify -Poracle-live} and {@code ORACLE_HEALTH_LIVE_IT=true}.
 */
@EnabledIfEnvironmentVariable(named = "ORACLE_HEALTH_LIVE_IT", matches = "true")
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE)
class OracleHealthSandboxAuthenticatedPatientSearchLiveIT {

    @Autowired
    private OracleSandboxAuthenticatedReadService oracleSandboxAuthenticatedReadService;

    @Autowired
    private OracleHealthIntegrationProfile oracleHealthSandboxProfile;

    @Test
    void configuredSandboxDiagnosesAuthenticatedSearchWithoutDumpingClinicalData() {
        assumeThat(oracleHealthSandboxProfile.enabled()).isTrue();
        assumeThat(oracleHealthSandboxProfile.fhirBaseUrl()).isNotBlank();

        FhirAuthenticatedReadResult result =
                oracleSandboxAuthenticatedReadService.searchPatients(oracleHealthSandboxProfile);

        assertThat(result.outcome()).isIn(
                FhirAuthenticatedReadOutcome.AUTHENTICATION_REQUIRED,
                FhirAuthenticatedReadOutcome.AUTHENTICATED_READ_SUCCEEDED,
                FhirAuthenticatedReadOutcome.AUTHENTICATION_REJECTED,
                FhirAuthenticatedReadOutcome.AUTHORIZATION_DENIED,
                FhirAuthenticatedReadOutcome.CAPABILITY_UNSUPPORTED,
                FhirAuthenticatedReadOutcome.DEPENDENCY_FAILURE);
        assertThat(result.destination()).isEqualTo(OracleHealthIntegrationProfile.SANDBOX_SERVER);
        assertThat(result.resourceType()).isEqualTo("Patient");
        assertThat(result.toString()).doesNotContain("access_token");
        assertThat(result.toString()).doesNotContain("Bearer ");
        assertThat(result.toString()).doesNotContain("Patient/");
        assertThat(result.detail()).doesNotContain("access_token");
    }
}
