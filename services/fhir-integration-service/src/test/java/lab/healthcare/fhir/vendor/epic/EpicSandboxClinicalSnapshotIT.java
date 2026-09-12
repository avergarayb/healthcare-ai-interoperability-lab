package lab.healthcare.fhir.vendor.epic;

import lab.healthcare.fhir.client.FhirService;
import lab.healthcare.fhir.server.FhirServerProfile;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotOutcome;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotResult;
import lab.healthcare.fhir.vendor.FhirVendor;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE)
class EpicSandboxClinicalSnapshotIT {

    @Autowired
    private EpicSandboxClinicalSnapshotService epicSandboxClinicalSnapshotService;

    @Autowired
    private EpicIntegrationProfile epicSandboxProfile;

    @Autowired
    private FhirServerProfile activeFhirServerProfile;

    @Autowired
    private FhirService fhirService;

    @Test
    void defaultDisabledEpicDoesNotAssembleSnapshot() {
        assertThat(activeFhirServerProfile.name()).isEqualTo("local-hapi");
        assertThat(activeFhirServerProfile.vendor()).isEqualTo(FhirVendor.GENERIC);
        assertThat(epicSandboxProfile.enabled()).isFalse();
        assertThat(epicSandboxProfile.hasConfiguredPatientId()).isFalse();

        ClinicalSnapshotResult result = epicSandboxClinicalSnapshotService.assemble(epicSandboxProfile);

        assertThat(result.outcome()).isEqualTo(ClinicalSnapshotOutcome.AUTHENTICATION_REQUIRED);
        assertThat(result.toString()).doesNotContain("access_token");
        assertThat(result.toString()).doesNotContain("Patient/");
        assertThat(fhirService).isNotNull();
    }
}
