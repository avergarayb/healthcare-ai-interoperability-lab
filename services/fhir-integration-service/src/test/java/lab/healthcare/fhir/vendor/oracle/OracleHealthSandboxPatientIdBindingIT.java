package lab.healthcare.fhir.vendor.oracle;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.TestPropertySource;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE)
@TestPropertySource(properties = "ORACLE_HEALTH_SANDBOX_PATIENT_ID=lab-configured-patient")
class OracleHealthSandboxPatientIdBindingIT {

    @Autowired
    private OracleHealthIntegrationProfile oracleHealthSandboxProfile;

    @Test
    void yamlBindsConfiguredPatientIdWithoutPrintingIt() {
        assertThat(oracleHealthSandboxProfile.hasConfiguredPatientId()).isTrue();
        assertThat(oracleHealthSandboxProfile.configuredPatientId()).isEqualTo("lab-configured-patient");
        assertThat(oracleHealthSandboxProfile.toString()).doesNotContain("lab-configured-patient");
    }
}
