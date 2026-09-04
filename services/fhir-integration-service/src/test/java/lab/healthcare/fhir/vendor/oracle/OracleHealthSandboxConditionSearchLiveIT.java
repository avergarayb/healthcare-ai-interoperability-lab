package lab.healthcare.fhir.vendor.oracle;

import lab.healthcare.fhir.routing.FhirConditionSearchOutcome;
import lab.healthcare.fhir.routing.FhirConditionSearchResult;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assumptions.assumeThat;

/**
 * Opt-in authenticated Condition SEARCH_TYPE. Excluded from {@code -Pintegration}.
 * Maven cannot complete browser login, so a missing session token is
 * {@code AUTHENTICATION_REQUIRED}. A missing Patient ID is
 * {@code PATIENT_CONTEXT_NOT_CONFIGURED}. Do not fabricate credentials or IDs.
 * Run with {@code mvn verify -Poracle-live} and {@code ORACLE_HEALTH_LIVE_IT=true}.
 */
@EnabledIfEnvironmentVariable(named = "ORACLE_HEALTH_LIVE_IT", matches = "true")
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE)
class OracleHealthSandboxConditionSearchLiveIT {

    @Autowired
    private OracleSandboxConditionSearchService oracleSandboxConditionSearchService;

    @Autowired
    private OracleHealthIntegrationProfile oracleHealthSandboxProfile;

    @Test
    void configuredSandboxDiagnosesConditionSearchWithoutDumpingClinicalData() {
        assumeThat(oracleHealthSandboxProfile.enabled()).isTrue();
        assumeThat(oracleHealthSandboxProfile.fhirBaseUrl()).isNotBlank();

        FhirConditionSearchResult result =
                oracleSandboxConditionSearchService.searchConditions(oracleHealthSandboxProfile);

        assertThat(result.outcome()).isIn(
                FhirConditionSearchOutcome.PATIENT_CONTEXT_NOT_CONFIGURED,
                FhirConditionSearchOutcome.AUTHENTICATION_REQUIRED,
                FhirConditionSearchOutcome.CONDITION_SEARCH_SUCCEEDED,
                FhirConditionSearchOutcome.AUTHENTICATION_REJECTED,
                FhirConditionSearchOutcome.AUTHORIZATION_DENIED,
                FhirConditionSearchOutcome.CAPABILITY_UNSUPPORTED,
                FhirConditionSearchOutcome.DEPENDENCY_FAILURE);
        assertThat(result.destination()).isEqualTo(OracleHealthIntegrationProfile.SANDBOX_SERVER);
        assertThat(result.resourceType()).isEqualTo("Condition");
        assertThat(result.toString()).doesNotContain("access_token");
        assertThat(result.toString()).doesNotContain("Bearer ");
        assertThat(result.toString()).doesNotContain("Condition/");
        assertThat(result.detail()).doesNotContain("access_token");
        if (oracleHealthSandboxProfile.hasConfiguredPatientId()) {
            assertThat(result.toString()).doesNotContain(oracleHealthSandboxProfile.configuredPatientId());
        }
    }
}
