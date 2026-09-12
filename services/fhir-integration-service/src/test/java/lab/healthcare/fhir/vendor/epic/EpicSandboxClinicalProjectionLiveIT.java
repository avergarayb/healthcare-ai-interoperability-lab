package lab.healthcare.fhir.vendor.epic;

import lab.healthcare.fhir.projection.ClinicalProjectionResult;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotOutcome;

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
 * Run with {@code EPIC_SANDBOX_LIVE_IT=true}.
 */
@EnabledIfEnvironmentVariable(named = "EPIC_SANDBOX_LIVE_IT", matches = "true")
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE)
class EpicSandboxClinicalProjectionLiveIT {

    @Autowired
    private EpicSandboxClinicalProjectionService epicSandboxClinicalProjectionService;

    @Autowired
    private EpicIntegrationProfile epicSandboxProfile;

    @Test
    void configuredSandboxDiagnosesProjectionWithoutDumpingClinicalData() {
        assumeThat(epicSandboxProfile.enabled()).isTrue();
        assumeThat(epicSandboxProfile.fhirBaseUrl()).isNotBlank();

        ClinicalProjectionResult result = epicSandboxClinicalProjectionService.assemble(epicSandboxProfile);

        assertThat(result.outcome()).isIn(
                ClinicalSnapshotOutcome.PATIENT_CONTEXT_NOT_CONFIGURED,
                ClinicalSnapshotOutcome.AUTHENTICATION_REQUIRED,
                ClinicalSnapshotOutcome.SNAPSHOT_COMPLETE,
                ClinicalSnapshotOutcome.SNAPSHOT_PARTIAL,
                ClinicalSnapshotOutcome.SNAPSHOT_UNAVAILABLE);
        assertThat(result.destination()).isEqualTo(EpicIntegrationProfile.SANDBOX_SERVER);
        assertThat(result.medicationRequests()).isNull();
        assertThat(result.toString()).doesNotContain("access_token");
        assertThat(result.toString()).doesNotContain("Bearer ");
        assertThat(result.toString()).doesNotContain("Patient/");
        assertThat(result.detail()).doesNotContain("access_token");
        if (epicSandboxProfile.hasConfiguredPatientId()) {
            assertThat(result.toString()).doesNotContain(epicSandboxProfile.configuredPatientId());
        }
    }
}
