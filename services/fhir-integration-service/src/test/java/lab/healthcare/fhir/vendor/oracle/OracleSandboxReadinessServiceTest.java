package lab.healthcare.fhir.vendor.oracle;

import lab.healthcare.fhir.connectivity.FhirConnectivityOutcome;
import lab.healthcare.fhir.connectivity.FhirConnectivityStatus;
import lab.healthcare.fhir.connectivity.FhirEndpointConnectivityVerifier;
import lab.healthcare.fhir.exception.FhirErrorCategory;
import lab.healthcare.fhir.server.FhirDeploymentEnvironment;
import lab.healthcare.fhir.server.FhirServersProperties;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class OracleSandboxReadinessServiceTest {

    @Mock
    private FhirEndpointConnectivityVerifier verifier;

    @Test
    void disabledProfileIsDisabledWithoutHttp() {
        OracleSandboxReadinessService service =
                new OracleSandboxReadinessService(new OracleSandboxProfileValidator(), verifier);

        OracleSandboxReadiness readiness = service.inspect(OracleHealthIntegrationProfileTest.completePublicPkce());

        assertThat(readiness.state()).isEqualTo(OracleSandboxReadinessState.DISABLED);
        assertThat(readiness.enabled()).isFalse();
        assertThat(readiness.toString()).doesNotContain("lab-oracle-placeholder");
        assertThat(service.checkConnectivity(OracleHealthIntegrationProfileTest.completePublicPkce()).outcome())
                .isEqualTo(FhirConnectivityOutcome.SKIPPED);
        verify(verifier, never()).verify(anyString());
    }

    @Test
    void enabledCompleteSandboxIsReadyForConnectivityCheck() {
        OracleSandboxReadinessService service =
                new OracleSandboxReadinessService(new OracleSandboxProfileValidator(), verifier);
        OracleHealthIntegrationProfile profile = OracleHealthIntegrationProfileTest.completePublicPkceEnabled();

        OracleSandboxReadiness readiness = service.inspect(profile);
        OracleSandboxConfiguration configuration = OracleSandboxConfiguration.from(profile);

        assertThat(readiness.state()).isEqualTo(OracleSandboxReadinessState.READY_FOR_CONNECTIVITY_CHECK);
        assertThat(readiness.deploymentEnvironment()).isEqualTo(FhirDeploymentEnvironment.SANDBOX);
        assertThat(configuration.enabled()).isTrue();
        assertThat(configuration.toString()).doesNotContain("client_secret");
        assertThat(configuration.toString()).contains("hasClientId=true");
    }

    @Test
    void enabledMissingConfigurationIsInvalidAndDoesNotProbe() {
        OracleSandboxReadinessService service =
                new OracleSandboxReadinessService(new OracleSandboxProfileValidator(), verifier);
        OracleHealthIntegrationProfile profile = enabledMissingClientId();

        OracleSandboxReadiness readiness = service.inspect(profile);

        assertThat(readiness.state()).isEqualTo(OracleSandboxReadinessState.INVALID_CONFIGURATION);
        assertThat(readiness.error()).isEqualTo(FhirErrorCategory.VALIDATION_ERROR);
        assertThatThrownBy(() -> service.checkConnectivity(profile))
                .isInstanceOf(OracleHealthProfileException.class)
                .hasMessageNotContaining("access_token");
        verify(verifier, never()).verify(anyString());
    }

    @Test
    void productionIsConfiguredNotReadyForSandboxConnectivity() {
        OracleSandboxReadinessService service =
                new OracleSandboxReadinessService(new OracleSandboxProfileValidator(), verifier);
        OracleHealthIntegrationProfile profile = OracleHealthIntegrationProfile.from(
                OracleHealthIntegrationProfileTest.oracleServer(true, OracleHealthIntegrationProfileTest.smartAuth()),
                new FhirServersProperties.VendorIntegrationSettings(
                        "PRODUCTION", "STANDALONE", "PATIENT", "PUBLIC_PKCE"));

        OracleSandboxReadiness readiness = service.inspect(profile);

        assertThat(readiness.state()).isEqualTo(OracleSandboxReadinessState.CONFIGURED);
        assertThat(readiness.deploymentEnvironment()).isEqualTo(FhirDeploymentEnvironment.PRODUCTION);
        assertThat(service.checkConnectivity(profile).outcome()).isEqualTo(FhirConnectivityOutcome.SKIPPED);
        verify(verifier, never()).verify(anyString());
    }

    @Test
    void connectivityCheckUsesVerifierOnlyAfterValidation() {
        when(verifier.verify(OracleHealthIntegrationProfileTest.SYNTHETIC_BASE))
                .thenReturn(FhirConnectivityStatus.reachable(200));
        OracleSandboxReadinessService service =
                new OracleSandboxReadinessService(new OracleSandboxProfileValidator(), verifier);

        FhirConnectivityStatus status =
                service.checkConnectivity(OracleHealthIntegrationProfileTest.completePublicPkceEnabled());

        assertThat(status.reachable()).isTrue();
        verify(verifier).verify(OracleHealthIntegrationProfileTest.SYNTHETIC_BASE);
    }

    private static OracleHealthIntegrationProfile enabledMissingClientId() {
        lab.healthcare.fhir.auth.FhirAuthenticationSettings auth =
                new lab.healthcare.fhir.auth.FhirAuthenticationSettings(
                        lab.healthcare.fhir.auth.FhirAuthenticationType.SMART_AUTHORIZATION_CODE,
                        null,
                        "",
                        "",
                        "http://127.0.0.1/does-not-contact-oracle/.well-known/smart-configuration",
                        "http://127.0.0.1:8081/smart/callback",
                        "patient/Patient.read",
                        OracleHealthIntegrationProfileTest.SYNTHETIC_BASE);
        return OracleHealthIntegrationProfile.from(
                OracleHealthIntegrationProfileTest.oracleServer(true, auth), null);
    }
}
