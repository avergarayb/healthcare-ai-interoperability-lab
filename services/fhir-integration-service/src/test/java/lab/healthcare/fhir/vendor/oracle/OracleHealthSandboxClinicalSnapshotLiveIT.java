package lab.healthcare.fhir.vendor.oracle;

import lab.healthcare.fhir.snapshot.ClinicalSnapshotOutcome;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotResult;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assumptions.assumeThat;

/**
 * Opt-in controlled clinical snapshot. Excluded from {@code -Pintegration}.
 * Maven cannot complete browser login, so a missing session token is
 * {@code AUTHENTICATION_REQUIRED}. A missing Patient ID is
 * {@code PATIENT_CONTEXT_NOT_CONFIGURED}. Do not fabricate credentials or IDs.
 * Run with {@code mvn verify -Poracle-live} and {@code ORACLE_HEALTH_LIVE_IT=true}.
 */
@EnabledIfEnvironmentVariable(named = "ORACLE_HEALTH_LIVE_IT", matches = "true")
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE)
class OracleHealthSandboxClinicalSnapshotLiveIT {

    @Autowired
    private OracleSandboxClinicalSnapshotService oracleSandboxClinicalSnapshotService;

    @Autowired
    private OracleHealthIntegrationProfile oracleHealthSandboxProfile;

    @Test
    void configuredSandboxDiagnosesSnapshotWithoutDumpingClinicalData() {
        assumeThat(oracleHealthSandboxProfile.enabled()).isTrue();
        assumeThat(oracleHealthSandboxProfile.fhirBaseUrl()).isNotBlank();

        ClinicalSnapshotResult result = oracleSandboxClinicalSnapshotService.assemble(oracleHealthSandboxProfile);

        assertThat(result.outcome()).isIn(
                ClinicalSnapshotOutcome.PATIENT_CONTEXT_NOT_CONFIGURED,
                ClinicalSnapshotOutcome.AUTHENTICATION_REQUIRED,
                ClinicalSnapshotOutcome.SNAPSHOT_COMPLETE,
                ClinicalSnapshotOutcome.SNAPSHOT_PARTIAL,
                ClinicalSnapshotOutcome.SNAPSHOT_UNAVAILABLE);
        assertThat(result.destination()).isEqualTo(OracleHealthIntegrationProfile.SANDBOX_SERVER);
        assertThat(result.toString()).doesNotContain("access_token");
        assertThat(result.toString()).doesNotContain("Bearer ");
        assertThat(result.toString()).doesNotContain("Patient/");
        assertThat(result.detail()).doesNotContain("access_token");
        if (oracleHealthSandboxProfile.hasConfiguredPatientId()) {
            assertThat(result.toString()).doesNotContain(oracleHealthSandboxProfile.configuredPatientId());
        }
    }
}
