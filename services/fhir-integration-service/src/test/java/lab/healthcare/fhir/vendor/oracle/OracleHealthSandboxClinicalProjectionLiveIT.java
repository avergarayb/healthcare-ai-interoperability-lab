package lab.healthcare.fhir.vendor.oracle;

import lab.healthcare.fhir.projection.ClinicalProjectionResult;
import lab.healthcare.fhir.projection.ProjectedCollection;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotOutcome;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotResourceStatus;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assumptions.assumeThat;

/**
 * Opt-in controlled clinical projection. Excluded from {@code -Pintegration}.
 * Maven cannot complete browser login, so a missing session token is
 * {@code AUTHENTICATION_REQUIRED}. A missing Patient ID is
 * {@code PATIENT_CONTEXT_NOT_CONFIGURED}. Do not fabricate credentials or IDs.
 * Run with {@code mvn verify -Poracle-live} and {@code ORACLE_HEALTH_LIVE_IT=true}.
 */
@EnabledIfEnvironmentVariable(named = "ORACLE_HEALTH_LIVE_IT", matches = "true")
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE)
class OracleHealthSandboxClinicalProjectionLiveIT {

    @Autowired
    private OracleSandboxClinicalProjectionService oracleSandboxClinicalProjectionService;

    @Autowired
    private OracleHealthIntegrationProfile oracleHealthSandboxProfile;

    @Test
    void configuredSandboxDiagnosesProjectionWithoutDumpingClinicalData() {
        assumeThat(oracleHealthSandboxProfile.enabled()).isTrue();
        assumeThat(oracleHealthSandboxProfile.fhirBaseUrl()).isNotBlank();

        ClinicalProjectionResult result = oracleSandboxClinicalProjectionService.assemble(oracleHealthSandboxProfile);

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
        assertRetentionCeiling(result.conditions());
        assertRetentionCeiling(result.observations());
        assertRetentionCeiling(result.diagnosticReports());
        assertRetentionCeiling(result.medicationRequests());
    }

    private static void assertRetentionCeiling(ProjectedCollection<?> collection) {
        if (collection == null || collection.status() != ClinicalSnapshotResourceStatus.SUCCESS) {
            return;
        }
        assertThat(collection.retainedCount()).isLessThanOrEqualTo(5);
        if (collection.receivedCount() != null && collection.receivedCount() > 5) {
            assertThat(collection.retainedCount()).isEqualTo(5);
            assertThat(collection.truncated()).isTrue();
            assertThat(collection.items()).hasSize(5);
        }
    }
}
