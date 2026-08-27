package lab.healthcare.fhir.client;

import org.junit.jupiter.api.Test;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class OAuth2TokenClientTest {

    private final OAuth2TokenClient client = new OAuth2TokenClient();

    @Test
    void parseResponseAcceptsValidToken() {
        AccessToken token = client.parseResponse(
                200,
                "{\"access_token\":\"lab-access-token\",\"token_type\":\"Bearer\",\"expires_in\":3600}");

        assertThat(token.value()).isEqualTo("lab-access-token");
        assertThat(token.expiresAt()).isAfter(Instant.now().plusSeconds(3500));
    }

    @Test
    void parseResponseRejectsMissingAccessToken() {
        assertThatThrownBy(() -> client.parseResponse(200, "{\"token_type\":\"Bearer\",\"expires_in\":3600}"))
                .isInstanceOf(OAuth2TokenException.class)
                .hasMessageContaining("OAuth token acquisition failed")
                .hasMessageContaining("access_token");
    }

    @Test
    void parseResponseRejectsInvalidRequest() {
        assertThatThrownBy(() -> client.parseResponse(400, "{\"error\":\"invalid_request\"}"))
                .isInstanceOf(OAuth2TokenException.class)
                .hasMessageContaining("HTTP 400")
                .hasMessageContaining("invalid_request");
    }

    @Test
    void parseResponseRejectsInvalidClient() {
        assertThatThrownBy(() -> client.parseResponse(401, "{\"error\":\"invalid_client\"}"))
                .isInstanceOf(OAuth2TokenException.class)
                .hasMessageContaining("HTTP 401")
                .hasMessageContaining("invalid_client");
    }

    @Test
    void parseResponseRejectsUnsupportedGrant() {
        assertThatThrownBy(() -> client.parseResponse(400, "{\"error\":\"unsupported_grant_type\"}"))
                .isInstanceOf(OAuth2TokenException.class)
                .hasMessageContaining("unsupported_grant_type");
    }

    @Test
    void parseResponseRejectsEmptyBody() {
        assertThatThrownBy(() -> client.parseResponse(200, " "))
                .isInstanceOf(OAuth2TokenException.class)
                .hasMessageContaining("empty response");
    }

    @Test
    void fetchAccessTokenRejectsNoneAuthentication() {
        assertThatThrownBy(() -> client.fetchAccessToken(FhirAuthenticationSettings.none()))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("OAuth2 client credentials");
    }

    @Test
    void fetchAccessTokenRejectsUnavailableEndpoint() {
        FhirAuthenticationSettings authentication = new FhirAuthenticationSettings(
                FhirAuthenticationType.OAUTH2_CLIENT_CREDENTIALS,
                "http://127.0.0.1:1/oauth/token",
                "lab-client",
                "lab-secret");

        assertThatThrownBy(() -> client.fetchAccessToken(authentication))
                .isInstanceOf(OAuth2TokenException.class)
                .hasMessageContaining("OAuth token endpoint unavailable");
    }

    @Test
    void parserHonorsExpiresInAgainstClock() {
        Clock clock = Clock.fixed(Instant.parse("2026-08-26T12:00:00Z"), ZoneOffset.UTC);
        OAuth2TokenResponseParser parser = new OAuth2TokenResponseParser(
                new com.fasterxml.jackson.databind.ObjectMapper(), clock);

        AccessToken token = parser.parse(
                200,
                "{\"access_token\":\"lab-access-token\",\"expires_in\":60}");

        assertThat(token.expiresAt()).isEqualTo(Instant.parse("2026-08-26T12:01:00Z"));
        assertThat(token.isUsableAt(Instant.parse("2026-08-26T12:00:40Z"), CachingAccessTokenProvider.EXPIRY_SKEW))
                .isFalse();
    }
}
