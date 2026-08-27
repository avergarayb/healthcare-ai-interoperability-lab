package lab.healthcare.fhir.client;

import org.junit.jupiter.api.Test;

import java.net.URI;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class AuthorizationCodeClientTest {

    private final AuthorizationCodeClient client = new AuthorizationCodeClient(
            java.net.http.HttpClient.newBuilder().followRedirects(java.net.http.HttpClient.Redirect.NEVER).build(),
            Clock.fixed(Instant.parse("2026-08-26T12:00:00Z"), ZoneOffset.UTC));

    @Test
    void authorizationUrlContainsRequiredOauthAndSmartParameters() {
        AuthorizationSession session = client.createAuthorization(smartSettings(), configuration());
        URI uri = URI.create(session.authorizationUrl());

        assertThat(uri.getPath()).isEqualTo("/authorize");
        String query = uri.getRawQuery();
        assertThat(query).contains("response_type=code");
        assertThat(query).contains("client_id=lab-smart-app");
        assertThat(query).contains("redirect_uri=http%3A%2F%2F127.0.0.1%3A8081%2Fsmart%2Fcallback");
        assertThat(query).contains("scope=patient%2FPatient.read%20patient%2FObservation.read");
        assertThat(query).contains("aud=http%3A%2F%2Flocalhost%3A8180%2Ffhir");
        assertThat(query).contains("code_challenge_method=S256");
        assertThat(query).contains("state=" + session.state());
        assertThat(query).contains("code_challenge=" + session.codeChallenge());
        assertThat(session.codeVerifier()).isNotBlank();
        assertThat(session.codeChallenge()).isEqualTo(Pkce.codeChallengeS256(session.codeVerifier()));
    }

    @Test
    void callbackRejectsMismatchedState() {
        assertThatThrownBy(() -> client.authorizationCodeFromRedirect(
                        "http://127.0.0.1:8081/smart/callback?code=abc&state=other", "expected"))
                .isInstanceOf(OAuth2TokenException.class)
                .hasMessageContaining("invalid state");
    }

    @Test
    void callbackAcceptsMatchingStateAndCode() {
        String code = client.authorizationCodeFromRedirect(
                "http://127.0.0.1:8081/smart/callback?code=auth-code-1&state=lab-state", "lab-state");

        assertThat(code).isEqualTo("auth-code-1");
    }

    @Test
    void parseTokenResponseReadsSmartFields() {
        AccessToken token = client.parseTokenResponse(
                200,
                """
                {
                  "access_token":"smart-access",
                  "token_type":"Bearer",
                  "expires_in":3600,
                  "refresh_token":"refresh-1",
                  "scope":"patient/Patient.read",
                  "patient":"patient-001"
                }
                """);

        assertThat(token.value()).isEqualTo("smart-access");
        assertThat(token.refreshToken()).isEqualTo("refresh-1");
        assertThat(token.scope()).isEqualTo("patient/Patient.read");
        assertThat(token.patient()).isEqualTo("patient-001");
        assertThat(token.expiresAt()).isEqualTo(Instant.parse("2026-08-26T13:00:00Z"));
    }

    @Test
    void parseTokenResponseRejectsMissingAccessToken() {
        assertThatThrownBy(() -> client.parseTokenResponse(200, "{\"refresh_token\":\"refresh-1\"}"))
                .isInstanceOf(OAuth2TokenException.class)
                .hasMessageContaining("access_token");
    }

    private static FhirAuthenticationSettings smartSettings() {
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

    private static SmartConfiguration configuration() {
        return new SmartConfiguration(
                "http://localhost:9090/authorize",
                "http://localhost:9090/oauth/token",
                List.of("patient/Patient.read"),
                List.of("code"),
                List.of("S256"),
                List.of("launch-standalone"));
    }
}
