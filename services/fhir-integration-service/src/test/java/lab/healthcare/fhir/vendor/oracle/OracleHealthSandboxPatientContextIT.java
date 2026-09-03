package lab.healthcare.fhir.vendor.oracle;

import lab.healthcare.fhir.client.FhirService;
import lab.healthcare.fhir.routing.FhirPatientReadOutcome;
import lab.healthcare.fhir.routing.FhirPatientReadResult;
import lab.healthcare.fhir.server.FhirServerProfile;
import lab.healthcare.fhir.vendor.FhirVendor;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE)
class OracleHealthSandboxPatientContextIT {

    @Autowired
    private OracleSandboxPatientContextService oracleSandboxPatientContextService;

    @Autowired
    private OracleHealthIntegrationProfile oracleHealthSandboxProfile;

    @Autowired
    private FhirServerProfile activeFhirServerProfile;

    @Autowired
    private FhirService fhirService;

    @Test
    void defaultDisabledOracleDoesNotReadPatient() {
        assertThat(activeFhirServerProfile.name()).isEqualTo("local-hapi");
        assertThat(activeFhirServerProfile.vendor()).isEqualTo(FhirVendor.GENERIC);
        assertThat(oracleHealthSandboxProfile.enabled()).isFalse();
        assertThat(oracleHealthSandboxProfile.hasConfiguredPatientId()).isFalse();

        FhirPatientReadResult result = oracleSandboxPatientContextService.readPatient(oracleHealthSandboxProfile);

        assertThat(result.outcome()).isEqualTo(FhirPatientReadOutcome.AUTHENTICATION_REQUIRED);
        assertThat(result.toString()).doesNotContain("access_token");
        assertThat(result.toString()).doesNotContain("Patient/");
        assertThat(fhirService).isNotNull();
    }
}
