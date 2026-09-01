package lab.healthcare.fhir.vendor.oracle;

import lab.healthcare.fhir.client.FhirService;
import lab.healthcare.fhir.connectivity.FhirConnectivityStatus;
import lab.healthcare.fhir.connectivity.FhirEndpointConnectivityVerifier;
import lab.healthcare.fhir.server.FhirServerProfile;
import lab.healthcare.fhir.vendor.FhirVendor;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE)
class OracleHealthSandboxReadinessIT {

    @Autowired
    private OracleSandboxReadinessService oracleSandboxReadinessService;

    @Autowired
    private OracleSandboxConfiguration oracleSandboxConfiguration;

    @Autowired
    private OracleHealthIntegrationProfile oracleHealthSandboxProfile;

    @Autowired
    private FhirServerProfile activeFhirServerProfile;

    @Autowired
    private FhirService fhirService;

    @Autowired
    private FhirEndpointConnectivityVerifier fhirEndpointConnectivityVerifier;

    @Test
    void defaultDisabledOracleDoesNotRequireCredentialsOrHttp() {
        assertThat(activeFhirServerProfile.name()).isEqualTo("local-hapi");
        assertThat(activeFhirServerProfile.vendor()).isEqualTo(FhirVendor.GENERIC);
        assertThat(oracleHealthSandboxProfile.enabled()).isFalse();
        assertThat(oracleSandboxConfiguration.enabled()).isFalse();
        assertThat(oracleSandboxConfiguration.fhirBaseUrl()).isEmpty();
        assertThat(oracleSandboxConfiguration.clientId()).isEmpty();

        OracleSandboxReadiness readiness = oracleSandboxReadinessService.inspect(oracleHealthSandboxProfile);
        assertThat(readiness.state()).isEqualTo(OracleSandboxReadinessState.DISABLED);
        assertThat(oracleSandboxReadinessService.checkConnectivity(oracleHealthSandboxProfile).outcome().name())
                .isEqualTo("SKIPPED");
        assertThat(readiness.toString()).doesNotContain("client_secret");
        assertThat(oracleSandboxConfiguration.toString()).doesNotContain("access_token");
        assertThat(fhirService).isNotNull();
    }

    @Test
    void localHapiMetadataIsReachableWithoutOracleCredentials() {
        FhirConnectivityStatus status = fhirEndpointConnectivityVerifier.verify("http://localhost:8080/fhir");

        assertThat(status.reachable()).isTrue();
        assertThat(status.httpStatus()).isEqualTo(200);
        assertThat(status.toString()).doesNotContain("ORACLE_HEALTH_SANDBOX_CLIENT_ID");
    }
}
