package lab.healthcare.fhir.vendor.oracle;

import lab.healthcare.fhir.routing.FhirMedicationRequestSearchOutcome;
import lab.healthcare.fhir.routing.FhirMedicationRequestSearchResult;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assumptions.assumeThat;

/**
 * Opt-in authenticated MedicationRequest SEARCH_TYPE. Excluded from {@code -Pintegration}.
 * Maven cannot complete browser login, so a missing session token is
 * {@code AUTHENTICATION_REQUIRED}. A missing Patient ID is
 * {@code PATIENT_CONTEXT_NOT_CONFIGURED}. Do not fabricate credentials or IDs.
 * Run with {@code mvn verify -Poracle-live} and {@code ORACLE_HEALTH_LIVE_IT=true}.
 */
@EnabledIfEnvironmentVariable(named = "ORACLE_HEALTH_LIVE_IT", matches = "true")
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE)
class OracleHealthSandboxMedicationRequestSearchLiveIT {

    @Autowired
    private OracleSandboxMedicationRequestSearchService oracleSandboxMedicationRequestSearchService;

    @Autowired
    private OracleHealthIntegrationProfile oracleHealthSandboxProfile;

    @Test
    void configuredSandboxDiagnosesMedicationRequestSearchWithoutDumpingClinicalData() {
        assumeThat(oracleHealthSandboxProfile.enabled()).isTrue();
        assumeThat(oracleHealthSandboxProfile.fhirBaseUrl()).isNotBlank();

        FhirMedicationRequestSearchResult result =
                oracleSandboxMedicationRequestSearchService.searchMedicationRequests(oracleHealthSandboxProfile);

        assertThat(result.outcome()).isIn(
                FhirMedicationRequestSearchOutcome.PATIENT_CONTEXT_NOT_CONFIGURED,
                FhirMedicationRequestSearchOutcome.AUTHENTICATION_REQUIRED,
                FhirMedicationRequestSearchOutcome.MEDICATION_REQUEST_SEARCH_SUCCEEDED,
                FhirMedicationRequestSearchOutcome.AUTHENTICATION_REJECTED,
                FhirMedicationRequestSearchOutcome.AUTHORIZATION_DENIED,
                FhirMedicationRequestSearchOutcome.CAPABILITY_UNSUPPORTED,
                FhirMedicationRequestSearchOutcome.DEPENDENCY_FAILURE);
        assertThat(result.destination()).isEqualTo(OracleHealthIntegrationProfile.SANDBOX_SERVER);
        assertThat(result.resourceType()).isEqualTo("MedicationRequest");
        assertThat(result.toString()).doesNotContain("access_token");
        assertThat(result.toString()).doesNotContain("Bearer ");
        assertThat(result.toString()).doesNotContain("MedicationRequest/");
        assertThat(result.detail()).doesNotContain("access_token");
        if (oracleHealthSandboxProfile.hasConfiguredPatientId()) {
            assertThat(result.toString()).doesNotContain(oracleHealthSandboxProfile.configuredPatientId());
        }
    }
}
