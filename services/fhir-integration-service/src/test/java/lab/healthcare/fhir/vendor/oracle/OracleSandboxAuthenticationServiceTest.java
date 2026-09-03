package lab.healthcare.fhir.vendor.oracle;

import lab.healthcare.fhir.auth.AccessToken;
import lab.healthcare.fhir.exception.FhirErrorCategory;
import lab.healthcare.fhir.server.FhirDeploymentEnvironment;
import lab.healthcare.fhir.server.FhirServersProperties;
import lab.healthcare.fhir.smart.AuthorizationCodeClient;
import lab.healthcare.fhir.smart.AuthorizationSession;
import lab.healthcare.fhir.smart.InMemoryAuthorizationSessionStore;
import lab.healthcare.fhir.smart.Pkce;
import lab.healthcare.fhir.smart.SmartAuthorizationCoordinator;
import lab.healthcare.fhir.smart.SmartAuthorizationStart;
import lab.healthcare.fhir.smart.SmartCompatibilityException;
import lab.healthcare.fhir.smart.SmartConfiguration;
import lab.healthcare.fhir.smart.SmartConfigurationClient;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class OracleSandboxAuthenticationServiceTest {

    private static final Clock CLOCK = Clock.fixed(Instant.parse("2026-09-01T12:00:00Z"), ZoneOffset.UTC);

    @Mock
    private SmartConfigurationClient smartConfigurationClient;

    @Mock
    private AuthorizationCodeClient authorizationCodeClient;

    @Test
    void disabledProfileIsInspectedWithoutHttp() {
        OracleSandboxAuthenticationService service = service();

        OracleSandboxAuthReadiness readiness =
                service.inspect(OracleHealthIntegrationProfileTest.completePublicPkce());

        assertThat(readiness.state()).isEqualTo(OracleSandboxAuthReadinessState.DISABLED);
        assertThat(readiness.enabled()).isFalse();
        assertThat(readiness.toString()).doesNotContain("lab-oracle-placeholder");
        assertThatThrownBy(() -> service.startAuthorization(OracleHealthIntegrationProfileTest.completePublicPkce()))
                .isInstanceOf(OracleHealthProfileException.class)
                .hasMessageContaining("disabled")
                .hasMessageNotContaining("access_token");
        verify(smartConfigurationClient, never()).fetch(anyString());
        verify(authorizationCodeClient, never()).createAuthorization(any(), any());
    }

    @Test
    void enabledCompleteSandboxIsReadyForAuthorization() {
        OracleSandboxAuthReadiness readiness =
                service().inspect(OracleHealthIntegrationProfileTest.completePublicPkceEnabled());

        assertThat(readiness.state()).isEqualTo(OracleSandboxAuthReadinessState.READY_FOR_AUTHORIZATION);
        assertThat(readiness.deploymentEnvironment()).isEqualTo(FhirDeploymentEnvironment.SANDBOX);
        assertThat(readiness.toString()).doesNotContain("client_secret");
    }

    @Test
    void startAuthorizationDiscoversSmartAndBuildsUrlWithAud() {
        when(smartConfigurationClient.fetch(anyString())).thenReturn(discovered());
        when(authorizationCodeClient.createAuthorization(any(), any()))
                .thenReturn(new AuthorizationSession(
                        "http://127.0.0.1/does-not-contact-oracle/authorize"
                                + "?response_type=code"
                                + "&aud=http%3A%2F%2F127.0.0.1%2Foracle-health-sandbox"
                                + "&code_challenge_method=S256"
                                + "&state=lab-state",
                        "lab-state",
                        "lab-pkce-verifier",
                        Pkce.codeChallengeS256("lab-pkce-verifier")));
        OracleHealthIntegrationProfile profile = OracleHealthIntegrationProfileTest.completePublicPkceEnabled();

        SmartAuthorizationStart start = service().startAuthorization(profile);

        assertThat(start.destination()).isEqualTo(OracleHealthIntegrationProfile.SANDBOX_SERVER);
        assertThat(start.authorizationUrl()).contains("response_type=code");
        assertThat(start.authorizationUrl()).contains("aud=http%3A%2F%2F127.0.0.1%2Foracle-health-sandbox");
        assertThat(start.authorizationUrl()).contains("code_challenge_method=S256");
        assertThat(start.toString()).doesNotContain("lab-pkce-verifier");
        verify(smartConfigurationClient).fetch(profile.smartConfigurationUrl());
    }

    @Test
    void privateKeyJwtIsRejectedWithoutDiscovery() {
        OracleHealthIntegrationProfile profile = OracleHealthIntegrationProfile.from(
                OracleHealthIntegrationProfileTest.oracleServer(true, OracleHealthIntegrationProfileTest.smartAuth()),
                FhirServersProperties.VendorIntegrationSettings.of(
                        "SANDBOX", "STANDALONE", "PATIENT", "PRIVATE_KEY_JWT"));
        OracleSandboxAuthenticationService service = service();

        OracleSandboxAuthReadiness readiness = service.inspect(profile);

        assertThat(readiness.state()).isEqualTo(OracleSandboxAuthReadinessState.INVALID_CONFIGURATION);
        assertThat(readiness.error()).isEqualTo(FhirErrorCategory.VALIDATION_ERROR);
        assertThatThrownBy(() -> service.startAuthorization(profile))
                .isInstanceOf(OracleHealthProfileException.class)
                .hasMessageContaining("PRIVATE_KEY_JWT")
                .hasMessageNotContaining("begin private key")
                .hasMessageNotContaining("client_secret=");
        verify(smartConfigurationClient, never()).fetch(anyString());
    }

    @Test
    void incompatibleSmartMetadataIsRejected() {
        when(smartConfigurationClient.fetch(anyString()))
                .thenReturn(new SmartConfiguration(
                        "http://127.0.0.1/does-not-contact-oracle/authorize",
                        "http://127.0.0.1/does-not-contact-oracle/token",
                        List.of(),
                        List.of("code"),
                        List.of("plain"),
                        List.of()));
        when(authorizationCodeClient.createAuthorization(any(), any()))
                .thenThrow(new SmartCompatibilityException("SMART metadata does not declare S256"));

        assertThatThrownBy(() ->
                        service().startAuthorization(OracleHealthIntegrationProfileTest.completePublicPkceEnabled()))
                .isInstanceOf(SmartCompatibilityException.class)
                .hasMessageContaining("S256");
    }

    @Test
    void completeAuthorizationExposesIssuedTokenProvider() {
        when(smartConfigurationClient.fetch(anyString())).thenReturn(discovered());
        when(authorizationCodeClient.createAuthorization(any(), any()))
                .thenReturn(new AuthorizationSession(
                        "http://127.0.0.1/authorize?state=lab-state",
                        "lab-state",
                        "lab-pkce-verifier",
                        Pkce.codeChallengeS256("lab-pkce-verifier")));
        AccessToken issued = new AccessToken(
                "oracle-access", Instant.parse("2026-09-01T13:00:00Z"), null, "patient/Patient.read", null);
        when(authorizationCodeClient.exchangeAuthorizationCode(any(), anyString(), anyString(), anyString()))
                .thenReturn(issued);
        OracleSandboxAuthenticationService service = service();
        service.startAuthorization(OracleHealthIntegrationProfileTest.completePublicPkceEnabled());

        AccessToken token = service.completeAuthorization(
                "http://127.0.0.1:8081/smart/callback?code=auth-code-1&state=lab-state");

        assertThat(token.value()).isEqualTo("oracle-access");
        assertThat(service.issuedTokenProvider().accessToken()).isEqualTo("oracle-access");
        assertThat(token.toString()).doesNotContain("oracle-access");
    }

    @Test
    void productionIsConfiguredNotReadyForAuthorization() {
        OracleHealthIntegrationProfile profile = OracleHealthIntegrationProfile.from(
                OracleHealthIntegrationProfileTest.oracleServer(true, OracleHealthIntegrationProfileTest.smartAuth()),
                FhirServersProperties.VendorIntegrationSettings.of(
                        "PRODUCTION", "STANDALONE", "PATIENT", "PUBLIC_PKCE"));
        OracleSandboxAuthenticationService service = service();

        OracleSandboxAuthReadiness readiness = service.inspect(profile);

        assertThat(readiness.state()).isEqualTo(OracleSandboxAuthReadinessState.CONFIGURED);
        assertThatThrownBy(() -> service.startAuthorization(profile))
                .isInstanceOf(OracleHealthProfileException.class)
                .hasMessageContaining("SANDBOX");
        verify(smartConfigurationClient, never()).fetch(anyString());
    }

    private OracleSandboxAuthenticationService service() {
        return new OracleSandboxAuthenticationService(
                new OracleSandboxProfileValidator(),
                smartConfigurationClient,
                new SmartAuthorizationCoordinator(
                        new InMemoryAuthorizationSessionStore(CLOCK), authorizationCodeClient, CLOCK));
    }

    private static SmartConfiguration discovered() {
        return new SmartConfiguration(
                "http://127.0.0.1/does-not-contact-oracle/authorize",
                "http://127.0.0.1/does-not-contact-oracle/token",
                List.of("patient/Patient.read"),
                List.of("code"),
                List.of("S256"),
                List.of());
    }
}
