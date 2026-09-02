package lab.healthcare.fhir.vendor.oracle;

import lab.healthcare.fhir.client.FhirService;
import lab.healthcare.fhir.server.FhirServerProfile;
import lab.healthcare.fhir.vendor.FhirVendor;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE)
class OracleHealthSandboxCapabilityIT {

    @Autowired
    private OracleSandboxCapabilityDiscoveryService oracleSandboxCapabilityDiscoveryService;

    @Autowired
    private OracleHealthIntegrationProfile oracleHealthSandboxProfile;

    @Autowired
    private FhirServerProfile activeFhirServerProfile;

    @Autowired
    private FhirService fhirService;

    @Test
    void defaultDisabledOracleDoesNotRequireNetworkOrCredentials() {
        assertThat(activeFhirServerProfile.name()).isEqualTo("local-hapi");
        assertThat(activeFhirServerProfile.vendor()).isEqualTo(FhirVendor.GENERIC);
        assertThat(oracleHealthSandboxProfile.enabled()).isFalse();

        OracleSandboxReadiness readiness =
                oracleSandboxCapabilityDiscoveryService.inspect(oracleHealthSandboxProfile);

        assertThat(readiness.state()).isEqualTo(OracleSandboxReadinessState.DISABLED);
        assertThatThrownBy(() -> oracleSandboxCapabilityDiscoveryService.discover(oracleHealthSandboxProfile))
                .isInstanceOf(OracleHealthProfileException.class)
                .hasMessageContaining("disabled")
                .hasMessageNotContaining("access_token");
        assertThat(readiness.toString()).doesNotContain("client_secret");
        assertThat(fhirService).isNotNull();
        assertThat(OracleHealthKnownApiSurface.assumesEveryR4Resource()).isFalse();
    }
}
