package lab.healthcare.fhir.vendor.epic;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.TestPropertySource;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE)
@TestPropertySource(properties = "EPIC_SANDBOX_PATIENT_ID=lab-configured-patient")
class EpicSandboxPatientIdBindingIT {

    @Autowired
    private EpicIntegrationProfile epicSandboxProfile;

    @Test
    void yamlBindsConfiguredPatientIdWithoutPrintingIt() {
        assertThat(epicSandboxProfile.hasConfiguredPatientId()).isTrue();
        assertThat(epicSandboxProfile.configuredPatientId()).isEqualTo("lab-configured-patient");
        assertThat(epicSandboxProfile.toString()).doesNotContain("lab-configured-patient");
    }
}
