package lab.healthcare.fhir.vendor.oracle;

import lab.healthcare.fhir.routing.FhirPatientReadOutcome;
import lab.healthcare.fhir.routing.FhirPatientReadResult;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assumptions.assumeThat;

/**
 * Opt-in authenticated Patient READ. Excluded from {@code -Pintegration}.
 * Maven cannot complete browser login, so a missing session token is
 * {@code AUTHENTICATION_REQUIRED}. A missing Patient ID is
 * {@code PATIENT_CONTEXT_NOT_CONFIGURED}. Do not fabricate credentials or IDs.
 * Run with {@code mvn verify -Poracle-live} and {@code ORACLE_HEALTH_LIVE_IT=true}.
 */
@EnabledIfEnvironmentVariable(named = "ORACLE_HEALTH_LIVE_IT", matches = "true")
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE)
class OracleHealthSandboxPatientContextLiveIT {

    @Autowired
    private OracleSandboxPatientContextService oracleSandboxPatientContextService;

    @Autowired
    private OracleHealthIntegrationProfile oracleHealthSandboxProfile;

    @Test
    void configuredSandboxDiagnosesControlledPatientReadWithoutDumpingClinicalData() {
        assumeThat(oracleHealthSandboxProfile.enabled()).isTrue();
        assumeThat(oracleHealthSandboxProfile.fhirBaseUrl()).isNotBlank();

        FhirPatientReadResult result = oracleSandboxPatientContextService.readPatient(oracleHealthSandboxProfile);

        assertThat(result.outcome()).isIn(
                FhirPatientReadOutcome.PATIENT_CONTEXT_NOT_CONFIGURED,
                FhirPatientReadOutcome.AUTHENTICATION_REQUIRED,
                FhirPatientReadOutcome.PATIENT_READ_SUCCEEDED,
                FhirPatientReadOutcome.AUTHENTICATION_REJECTED,
                FhirPatientReadOutcome.AUTHORIZATION_DENIED,
                FhirPatientReadOutcome.PATIENT_NOT_FOUND,
                FhirPatientReadOutcome.CAPABILITY_UNSUPPORTED,
                FhirPatientReadOutcome.DEPENDENCY_FAILURE);
        assertThat(result.destination()).isEqualTo(OracleHealthIntegrationProfile.SANDBOX_SERVER);
        assertThat(result.resourceType()).isEqualTo("Patient");
        assertThat(result.toString()).doesNotContain("access_token");
        assertThat(result.toString()).doesNotContain("Bearer ");
        assertThat(result.toString()).doesNotContain("Patient/");
        assertThat(result.detail()).doesNotContain("access_token");
        if (oracleHealthSandboxProfile.hasConfiguredPatientId()) {
            assertThat(result.toString()).doesNotContain(oracleHealthSandboxProfile.configuredPatientId());
        }
    }
}
