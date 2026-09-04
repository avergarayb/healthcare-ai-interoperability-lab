package lab.healthcare.fhir.vendor.oracle;

import lab.healthcare.fhir.routing.FhirObservationSearchOutcome;
import lab.healthcare.fhir.routing.FhirObservationSearchResult;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assumptions.assumeThat;

/**
 * Opt-in authenticated Observation SEARCH_TYPE. Excluded from {@code -Pintegration}.
 * Maven cannot complete browser login, so a missing session token is
 * {@code AUTHENTICATION_REQUIRED}. A missing Patient ID is
 * {@code PATIENT_CONTEXT_NOT_CONFIGURED}. Do not fabricate credentials or IDs.
 * Run with {@code mvn verify -Poracle-live} and {@code ORACLE_HEALTH_LIVE_IT=true}.
 */
@EnabledIfEnvironmentVariable(named = "ORACLE_HEALTH_LIVE_IT", matches = "true")
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE)
class OracleHealthSandboxObservationSearchLiveIT {

    @Autowired
    private OracleSandboxObservationSearchService oracleSandboxObservationSearchService;

    @Autowired
    private OracleHealthIntegrationProfile oracleHealthSandboxProfile;

    @Test
    void configuredSandboxDiagnosesObservationSearchWithoutDumpingClinicalData() {
        assumeThat(oracleHealthSandboxProfile.enabled()).isTrue();
        assumeThat(oracleHealthSandboxProfile.fhirBaseUrl()).isNotBlank();

        FhirObservationSearchResult result =
                oracleSandboxObservationSearchService.searchObservations(oracleHealthSandboxProfile);

        assertThat(result.outcome()).isIn(
                FhirObservationSearchOutcome.PATIENT_CONTEXT_NOT_CONFIGURED,
                FhirObservationSearchOutcome.AUTHENTICATION_REQUIRED,
                FhirObservationSearchOutcome.OBSERVATION_SEARCH_SUCCEEDED,
                FhirObservationSearchOutcome.AUTHENTICATION_REJECTED,
                FhirObservationSearchOutcome.AUTHORIZATION_DENIED,
                FhirObservationSearchOutcome.CAPABILITY_UNSUPPORTED,
                FhirObservationSearchOutcome.DEPENDENCY_FAILURE);
        assertThat(result.destination()).isEqualTo(OracleHealthIntegrationProfile.SANDBOX_SERVER);
        assertThat(result.resourceType()).isEqualTo("Observation");
        assertThat(result.toString()).doesNotContain("access_token");
        assertThat(result.toString()).doesNotContain("Bearer ");
        assertThat(result.toString()).doesNotContain("Observation/");
        assertThat(result.detail()).doesNotContain("access_token");
        if (oracleHealthSandboxProfile.hasConfiguredPatientId()) {
            assertThat(result.toString()).doesNotContain(oracleHealthSandboxProfile.configuredPatientId());
        }
    }
}
