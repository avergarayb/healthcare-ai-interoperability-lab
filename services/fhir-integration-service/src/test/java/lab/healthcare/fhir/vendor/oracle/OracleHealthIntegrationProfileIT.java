package lab.healthcare.fhir.vendor.oracle;

import lab.healthcare.fhir.client.FhirService;
import lab.healthcare.fhir.server.FhirServerProfile;
import lab.healthcare.fhir.server.FhirServerProfileRegistry;
import lab.healthcare.fhir.vendor.FhirVendor;
import lab.healthcare.fhir.vendor.epic.EpicIntegrationProfile;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE)
class OracleHealthIntegrationProfileIT {

    @Autowired
    private OracleHealthIntegrationProfile oracleHealthSandboxProfile;

    @Autowired
    private EpicIntegrationProfile epicSandboxProfile;

    @Autowired
    private FhirServerProfile activeFhirServerProfile;

    @Autowired
    private FhirServerProfileRegistry registry;

    @Autowired
    private FhirService fhirService;

    @Autowired
    private OracleHealthProfileValidator oracleHealthProfileValidator;

    @Test
    void defaultYamlBindsDisabledOracleSandboxWithoutCredentials() {
        assertThat(activeFhirServerProfile.name()).isEqualTo("local-hapi");
        assertThat(activeFhirServerProfile.vendor()).isEqualTo(FhirVendor.GENERIC);
        assertThat(registry.profile("oracle-health-sandbox").enabled()).isFalse();
        assertThat(registry.profile("oracle-health-sandbox").vendor()).isEqualTo(FhirVendor.ORACLE_HEALTH);
        assertThat(registry.profile("oracle-health-sandbox").baseUrl()).isEmpty();
        assertThat(oracleHealthSandboxProfile.vendor()).isEqualTo(FhirVendor.ORACLE_HEALTH);
        assertThat(oracleHealthSandboxProfile.enabled()).isFalse();
        assertThat(oracleHealthSandboxProfile.environment()).isEqualTo(OracleHealthEnvironment.SANDBOX);
        assertThat(oracleHealthSandboxProfile.fhirBaseUrl()).isEmpty();
        assertThat(oracleHealthSandboxProfile.aud()).isEmpty();
        assertThat(oracleHealthSandboxProfile.clientId()).isEmpty();
        assertThat(oracleHealthSandboxProfile.readiness()).isEqualTo(OracleHealthReadinessState.NOT_CONFIGURED);
        assertThat(oracleHealthSandboxProfile.clientAuthentication())
                .isEqualTo(OracleHealthClientAuthentication.PUBLIC_PKCE);
        assertThatCode(() -> oracleHealthProfileValidator.validate(oracleHealthSandboxProfile))
                .doesNotThrowAnyException();
        assertThat(fhirService).isNotNull();
        assertThat(epicSandboxProfile.vendor()).isEqualTo(FhirVendor.EPIC);
        assertThat(epicSandboxProfile.enabled()).isFalse();
        assertThat(oracleHealthSandboxProfile.toString()).doesNotContain("client_secret");
    }
}
