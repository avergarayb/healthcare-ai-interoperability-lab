package lab.healthcare.fhir.vendor.oracle;

import lab.healthcare.fhir.server.FhirServerProfile;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest(
        webEnvironment = SpringBootTest.WebEnvironment.NONE,
        properties = {
            "fhir.active-server=local-hapi",
            "fhir.servers.oracle-health-sandbox.enabled=true",
            "fhir.servers.oracle-health-sandbox.base-url=http://127.0.0.1/oracle-health-sandbox",
            "fhir.servers.oracle-health-sandbox.authentication.client-id=lab-oracle-placeholder",
            "fhir.servers.oracle-health-sandbox.authentication.redirect-uri=http://127.0.0.1:8081/smart/callback",
            "fhir.servers.oracle-health-sandbox.authentication.scope=patient/Patient.read",
            "fhir.servers.oracle-health-sandbox.authentication.aud=http://127.0.0.1/oracle-health-sandbox",
            "fhir.servers.oracle-health-sandbox.authentication.smart-configuration-url="
                    + "http://127.0.0.1/does-not-contact-oracle/.well-known/smart-configuration"
        })
class OracleHealthSandboxReadinessConfiguredIT {

    @Autowired
    private OracleSandboxReadinessService oracleSandboxReadinessService;

    @Autowired
    private OracleHealthIntegrationProfile oracleHealthSandboxProfile;

    @Autowired
    private FhirServerProfile activeFhirServerProfile;

    @Test
    void enabledSyntheticSandboxIsReadyForConnectivityWithoutCallingOracle() {
        assertThat(activeFhirServerProfile.name()).isEqualTo("local-hapi");
        assertThat(oracleHealthSandboxProfile.enabled()).isTrue();
        assertThat(oracleHealthSandboxProfile.fhirBaseUrl()).startsWith("http://127.0.0.1/");

        OracleSandboxReadiness readiness = oracleSandboxReadinessService.inspect(oracleHealthSandboxProfile);

        assertThat(readiness.state()).isEqualTo(OracleSandboxReadinessState.READY_FOR_CONNECTIVITY_CHECK);
        assertThat(readiness.toString()).doesNotContain("lab-oracle-placeholder");
        assertThat(oracleHealthSandboxProfile.toString()).doesNotContain("client_secret");
    }
}
