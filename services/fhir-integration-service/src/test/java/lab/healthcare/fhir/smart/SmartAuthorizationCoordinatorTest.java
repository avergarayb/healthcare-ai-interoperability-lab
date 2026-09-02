package lab.healthcare.fhir.smart;

import lab.healthcare.fhir.auth.AccessToken;
import lab.healthcare.fhir.auth.FhirAuthenticationSettings;
import lab.healthcare.fhir.auth.FhirAuthenticationType;
import lab.healthcare.fhir.auth.IssuedAccessTokenProvider;
import lab.healthcare.fhir.auth.oauth2.OAuth2TokenException;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.net.URI;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class SmartAuthorizationCoordinatorTest {

    private final Clock clock = Clock.fixed(Instant.parse("2026-09-01T12:00:00Z"), ZoneOffset.UTC);

    @Mock
    private AuthorizationCodeClient authorizationCodeClient;

    @Test
    void startBuildsAuthorizationUrlWithAudAndPkceS256() {
        AuthorizationCodeClient realClient = new AuthorizationCodeClient();
        SmartAuthorizationCoordinator coordinator = new SmartAuthorizationCoordinator(
                new InMemoryAuthorizationSessionStore(clock), realClient, clock);

        SmartAuthorizationStart start = coordinator.start(smartSettings(), configuration(), "smart-lab");
        URI uri = URI.create(start.authorizationUrl());

        assertThat(start.destination()).isEqualTo("smart-lab");
        assertThat(uri.getPath()).isEqualTo("/authorize");
        assertThat(start.authorizationUrl()).contains("response_type=code");
        assertThat(start.authorizationUrl()).contains("aud=http%3A%2F%2Flocalhost%3A8180%2Ffhir");
        assertThat(start.authorizationUrl()).contains("code_challenge_method=S256");
        assertThat(start.authorizationUrl()).contains("state=" + start.state());
        assertThat(start.expiresAt()).isEqualTo(Instant.parse("2026-09-01T12:10:00Z"));
        assertThat(start.toString()).doesNotContain("code_verifier");
        assertThat(start.toString()).doesNotContain("access_token");
    }

    @Test
    void startRejectsIncompatibleSmartMetadata() {
        AuthorizationCodeClient realClient = new AuthorizationCodeClient();
        SmartAuthorizationCoordinator coordinator = new SmartAuthorizationCoordinator(
                new InMemoryAuthorizationSessionStore(clock), realClient, clock);
        SmartConfiguration incompatible = new SmartConfiguration(
                "http://localhost:9090/authorize",
                "http://localhost:9090/oauth/token",
                List.of(),
                List.of("code"),
                List.of("plain"),
                List.of());

        assertThatThrownBy(() -> coordinator.start(smartSettings(), incompatible, "smart-lab"))
                .isInstanceOf(SmartCompatibilityException.class)
                .hasMessageContaining("S256")
                .hasMessageNotContaining("code_verifier");
    }

    @Test
    void completeExchangesCodeAfterMatchingState() {
        InMemoryAuthorizationSessionStore store = new InMemoryAuthorizationSessionStore(clock);
        when(authorizationCodeClient.createAuthorization(any(), any()))
                .thenReturn(new AuthorizationSession(
                        "http://localhost:9090/authorize?state=lab-state",
                        "lab-state",
                        "lab-pkce-verifier",
                        Pkce.codeChallengeS256("lab-pkce-verifier")));
        AccessToken issued = new AccessToken(
                "smart-access", Instant.parse("2026-09-01T13:00:00Z"), "refresh-1", "patient/Patient.read", null);
        when(authorizationCodeClient.exchangeAuthorizationCode(any(), anyString(), eq("auth-code-1"), eq("lab-pkce-verifier")))
                .thenReturn(issued);
        SmartAuthorizationCoordinator coordinator =
                new SmartAuthorizationCoordinator(store, authorizationCodeClient, clock);
        coordinator.start(smartSettings(), configuration(), "smart-lab");

        AccessToken token = coordinator.complete(
                "http://127.0.0.1:8081/smart/callback?code=auth-code-1&state=lab-state");

        assertThat(token.value()).isEqualTo("smart-access");
        assertThat(token.toString()).doesNotContain("smart-access");
        assertThat(token.toString()).doesNotContain("refresh-1");
        IssuedAccessTokenProvider provider = new IssuedAccessTokenProvider(token);
        assertThat(provider.accessToken()).isEqualTo("smart-access");
    }

    @Test
    void mismatchedStateDoesNotExchangeToken() {
        InMemoryAuthorizationSessionStore store = new InMemoryAuthorizationSessionStore(clock);
        when(authorizationCodeClient.createAuthorization(any(), any()))
                .thenReturn(new AuthorizationSession(
                        "http://localhost:9090/authorize?state=lab-state",
                        "lab-state",
                        "lab-pkce-verifier",
                        Pkce.codeChallengeS256("lab-pkce-verifier")));
        SmartAuthorizationCoordinator coordinator =
                new SmartAuthorizationCoordinator(store, authorizationCodeClient, clock);
        coordinator.start(smartSettings(), configuration(), "smart-lab");

        assertThatThrownBy(() -> coordinator.complete(
                        "http://127.0.0.1:8081/smart/callback?code=auth-code-1&state=other"))
                .isInstanceOf(SmartAuthorizationException.class)
                .hasMessageContaining("unknown or expired")
                .hasMessageNotContaining("auth-code-1")
                .hasMessageNotContaining("lab-pkce-verifier");
        verify(authorizationCodeClient, never()).exchangeAuthorizationCode(any(), anyString(), anyString(), anyString());
    }

    @Test
    void callbackWithoutCodeDoesNotExchangeToken() {
        InMemoryAuthorizationSessionStore store = new InMemoryAuthorizationSessionStore(clock);
        when(authorizationCodeClient.createAuthorization(any(), any()))
                .thenReturn(new AuthorizationSession(
                        "http://localhost:9090/authorize?state=lab-state",
                        "lab-state",
                        "lab-pkce-verifier",
                        Pkce.codeChallengeS256("lab-pkce-verifier")));
        SmartAuthorizationCoordinator coordinator =
                new SmartAuthorizationCoordinator(store, authorizationCodeClient, clock);
        coordinator.start(smartSettings(), configuration(), "smart-lab");

        SmartTokenExchangeResult result = coordinator.completeDiagnosed(
                "http://127.0.0.1:8081/smart/callback?state=lab-state&error=access_denied");

        assertThat(result.succeeded()).isFalse();
        assertThat(result.diagnosis().incompatibility())
                .isEqualTo(SmartTokenAuthenticationIncompatibility.AUTHORIZATION_REJECTED);
        assertThat(result.diagnosis().oauthError()).isEqualTo("access_denied");
        assertThat(result.toString()).doesNotContain("lab-pkce-verifier");
        verify(authorizationCodeClient, never()).exchangeAuthorizationCode(any(), anyString(), anyString(), anyString());
    }

    @Test
    void expiredSessionDoesNotExchangeToken() {
        Clock later = Clock.fixed(Instant.parse("2026-09-01T12:11:00Z"), ZoneOffset.UTC);
        InMemoryAuthorizationSessionStore store = new InMemoryAuthorizationSessionStore(later);
        store.save(new PendingAuthorizationSession(
                "smart-lab",
                "lab-state",
                "lab-pkce-verifier",
                Pkce.codeChallengeS256("lab-pkce-verifier"),
                "http://localhost:9090/authorize",
                "http://localhost:9090/oauth/token",
                "lab-smart-app",
                "http://127.0.0.1:8081/smart/callback",
                Instant.parse("2026-09-01T12:10:00Z")));
        SmartAuthorizationCoordinator coordinator =
                new SmartAuthorizationCoordinator(store, authorizationCodeClient, later);

        assertThatThrownBy(() -> coordinator.complete(
                        "http://127.0.0.1:8081/smart/callback?code=auth-code-1&state=lab-state"))
                .isInstanceOf(SmartAuthorizationException.class)
                .hasMessageContaining("unknown or expired");
        verify(authorizationCodeClient, never()).exchangeAuthorizationCode(any(), anyString(), anyString(), anyString());
    }

    @Test
    void rejectedTokenExchangeDiagnosesConfidentialAuthFromDiscovery() {
        InMemoryAuthorizationSessionStore store = new InMemoryAuthorizationSessionStore(clock);
        when(authorizationCodeClient.createAuthorization(any(), any()))
                .thenReturn(new AuthorizationSession(
                        "http://localhost:9090/authorize?state=lab-state",
                        "lab-state",
                        "lab-pkce-verifier",
                        Pkce.codeChallengeS256("lab-pkce-verifier")));
        when(authorizationCodeClient.exchangeAuthorizationCode(any(), anyString(), anyString(), anyString()))
                .thenThrow(new OAuth2TokenException(
                        "OAuth token acquisition failed: HTTP 401 invalid_client",
                        401,
                        "invalid_client",
                        null));
        SmartAuthorizationCoordinator coordinator =
                new SmartAuthorizationCoordinator(store, authorizationCodeClient, clock);
        SmartAuthorizationStart start = coordinator.start(smartSettings(), oracleShapedDiscovery(), "oracle-health-sandbox");

        SmartTokenExchangeResult result = coordinator.completeDiagnosed(
                "http://localhost:8081/smart/callback?code=auth-code-1&state=lab-state");

        assertThat(start.advertisesConfidentialTokenAuth()).isTrue();
        assertThat(start.tokenEndpointAuthMethodsSupported())
                .containsExactly("client_secret_basic", "private_key_jwt");
        assertThat(result.succeeded()).isFalse();
        assertThat(result.diagnosis().incompatibility())
                .isEqualTo(SmartTokenAuthenticationIncompatibility.CONFIDENTIAL_CLIENT_REQUIRED);
        assertThat(result.diagnosis().nextArchitecturalChange()).contains("private_key_jwt");
        assertThat(result.diagnosis().nextArchitecturalChange()).contains("client_secret_basic");
        assertThat(result.toString()).doesNotContain("auth-code-1");
        assertThat(result.toString()).doesNotContain("lab-pkce-verifier");
    }

    @Test
    void pendingSessionToStringOmitsVerifier() {
        PendingAuthorizationSession session = new PendingAuthorizationSession(
                "smart-lab",
                "lab-state",
                "lab-pkce-verifier",
                Pkce.codeChallengeS256("lab-pkce-verifier"),
                "http://localhost:9090/authorize",
                "http://localhost:9090/oauth/token",
                "lab-smart-app",
                "http://127.0.0.1:8081/smart/callback",
                Instant.parse("2026-09-01T12:10:00Z"));

        assertThat(session.toString()).doesNotContain("lab-pkce-verifier");
        assertThat(session.toString()).doesNotContain("code_verifier=");
        assertThat(new AuthorizationSession(
                        "http://localhost:9090/authorize",
                        "lab-state",
                        "lab-pkce-verifier",
                        Pkce.codeChallengeS256("lab-pkce-verifier"))
                .toString())
                .doesNotContain("lab-pkce-verifier");
    }

    static FhirAuthenticationSettings smartSettings() {
        return new FhirAuthenticationSettings(
                FhirAuthenticationType.SMART_AUTHORIZATION_CODE,
                null,
                "lab-smart-app",
                "",
                "http://localhost:8180/fhir/.well-known/smart-configuration",
                "http://127.0.0.1:8081/smart/callback",
                "patient/Patient.read patient/Observation.read",
                "http://localhost:8180/fhir");
    }

    static SmartConfiguration configuration() {
        return new SmartConfiguration(
                "http://localhost:9090/authorize",
                "http://localhost:9090/oauth/token",
                List.of("patient/Patient.read"),
                List.of("code"),
                List.of("S256"),
                List.of("launch-standalone"));
    }

    static SmartConfiguration oracleShapedDiscovery() {
        return new SmartConfiguration(
                "http://127.0.0.1/does-not-contact-oracle/authorize",
                "http://127.0.0.1/does-not-contact-oracle/token",
                null,
                List.of("user/Patient.read"),
                List.of("code"),
                List.of("authorization_code"),
                List.of("S256"),
                List.of("client-public", "client-confidential-symmetric", "client-confidential-asymmetric"),
                List.of("client_secret_basic", "private_key_jwt"));
    }
}
