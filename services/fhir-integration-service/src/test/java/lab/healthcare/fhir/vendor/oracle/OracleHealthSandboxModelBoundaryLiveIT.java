package lab.healthcare.fhir.vendor.oracle;

import lab.healthcare.fhir.modelboundary.BoundaryCollection;
import lab.healthcare.fhir.modelboundary.ModelBoundaryContract;
import lab.healthcare.fhir.modelboundary.ModelBoundaryContractVersion;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotOutcome;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotResourceStatus;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assumptions.assumeThat;

/**
 * Opt-in vendor-neutral model boundary. Excluded from {@code -Pintegration}.
 * Maven cannot complete browser login, so a missing session token is
 * {@code AUTHENTICATION_REQUIRED}. Do not fabricate credentials or IDs.
 * Run with {@code mvn verify -Poracle-live} and {@code ORACLE_HEALTH_LIVE_IT=true}.
 */
@EnabledIfEnvironmentVariable(named = "ORACLE_HEALTH_LIVE_IT", matches = "true")
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE)
class OracleHealthSandboxModelBoundaryLiveIT {

    @Autowired
    private OracleSandboxModelBoundaryService oracleSandboxModelBoundaryService;

    @Autowired
    private OracleHealthIntegrationProfile oracleHealthSandboxProfile;

    @Test
    void configuredSandboxMapsProjectionWithoutDumpingClinicalData() {
        assumeThat(oracleHealthSandboxProfile.enabled()).isTrue();
        assumeThat(oracleHealthSandboxProfile.fhirBaseUrl()).isNotBlank();

        ModelBoundaryContract contract = oracleSandboxModelBoundaryService.assemble(oracleHealthSandboxProfile);

        assertThat(contract.contractVersion()).isEqualTo(ModelBoundaryContractVersion.V1);
        assertThat(contract.outcome()).isIn(
                ClinicalSnapshotOutcome.PATIENT_CONTEXT_NOT_CONFIGURED,
                ClinicalSnapshotOutcome.AUTHENTICATION_REQUIRED,
                ClinicalSnapshotOutcome.SNAPSHOT_COMPLETE,
                ClinicalSnapshotOutcome.SNAPSHOT_PARTIAL,
                ClinicalSnapshotOutcome.SNAPSHOT_UNAVAILABLE);
        assertThat(contract.destination()).isEqualTo(OracleHealthIntegrationProfile.SANDBOX_SERVER);
        assertThat(contract.toString()).doesNotContain("access_token");
        assertThat(contract.toString()).doesNotContain("Bearer ");
        assertThat(contract.toString()).doesNotContain("Patient/");
        if (oracleHealthSandboxProfile.hasConfiguredPatientId()) {
            assertThat(contract.toString()).doesNotContain(oracleHealthSandboxProfile.configuredPatientId());
        }
        assertRetentionCeiling(contract.conditions());
        assertRetentionCeiling(contract.observations());
        assertRetentionCeiling(contract.diagnosticReports());
        assertRetentionCeiling(contract.medicationRequests());
    }

    private static void assertRetentionCeiling(BoundaryCollection<?> collection) {
        if (collection == null || collection.status() != ClinicalSnapshotResourceStatus.SUCCESS) {
            return;
        }
        assertThat(collection.retainedCount()).isLessThanOrEqualTo(5);
        if (collection.receivedCount() != null && collection.receivedCount() > 5) {
            assertThat(collection.retainedCount()).isEqualTo(5);
            assertThat(collection.truncated()).isTrue();
            assertThat(collection.records()).hasSize(5);
        }
    }
}
