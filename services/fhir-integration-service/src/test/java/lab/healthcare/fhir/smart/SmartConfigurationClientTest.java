package lab.healthcare.fhir.smart;

import lab.healthcare.fhir.auth.oauth2.OAuth2TokenException;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class SmartConfigurationClientTest {

    private final SmartConfigurationClient client = new SmartConfigurationClient();

    @Test
    void parseReadsRequiredSmartDiscoveryFields() {
        SmartConfiguration configuration = client.parse(
                200,
                """
                {
                  "authorization_endpoint": "http://localhost:9090/authorize",
                  "token_endpoint": "http://localhost:9090/oauth/token",
                  "scopes_supported": ["patient/Patient.read", "patient/Observation.read"],
                  "response_types_supported": ["code"],
                  "code_challenge_methods_supported": ["S256"],
                  "capabilities": ["launch-standalone", "client-public"]
                }
                """);

        assertThat(configuration.authorizationEndpoint()).isEqualTo("http://localhost:9090/authorize");
        assertThat(configuration.tokenEndpoint()).isEqualTo("http://localhost:9090/oauth/token");
        assertThat(configuration.issuer()).isNull();
        assertThat(configuration.scopesSupported()).contains("patient/Patient.read", "patient/Observation.read");
        assertThat(configuration.responseTypesSupported()).containsExactly("code");
        assertThat(configuration.grantTypesSupported()).isEmpty();
        assertThat(configuration.codeChallengeMethodsSupported()).containsExactly("S256");
        assertThat(configuration.capabilities()).contains("launch-standalone", "client-public");
        assertThat(configuration.tokenEndpointAuthMethodsSupported()).isEmpty();
    }

    @Test
    void parseReadsTokenEndpointAuthMethodsWithoutInventingNone() {
        SmartConfiguration configuration = client.parse(
                200,
                """
                {
                  "authorization_endpoint": "http://127.0.0.1/does-not-contact-oracle/authorize",
                  "token_endpoint": "http://127.0.0.1/does-not-contact-oracle/token",
                  "grant_types_supported": ["authorization_code"],
                  "response_types_supported": ["code"],
                  "code_challenge_methods_supported": ["S256"],
                  "capabilities": ["client-public", "client-confidential-symmetric", "client-confidential-asymmetric"],
                  "token_endpoint_auth_methods_supported": ["client_secret_basic", "private_key_jwt"]
                }
                """);

        assertThat(configuration.tokenEndpointAuthMethodsSupported())
                .containsExactly("client_secret_basic", "private_key_jwt");
        assertThat(configuration.tokenEndpointAuthMethodsSupported()).doesNotContain("none");
        assertThat(SmartTokenExchangeDiagnoser.advertisesConfidentialTokenAuth(
                        configuration.tokenEndpointAuthMethodsSupported()))
                .isTrue();
    }

    @Test
    void parseReadsOptionalIssuerAndGrantTypes() {
        SmartConfiguration configuration = client.parse(
                200,
                """
                {
                  "authorization_endpoint": "http://localhost:9090/authorize",
                  "token_endpoint": "http://localhost:9090/oauth/token",
                  "issuer": "http://localhost:9090/",
                  "grant_types_supported": ["authorization_code", "refresh_token"]
                }
                """);

        assertThat(configuration.issuer()).isEqualTo("http://localhost:9090/");
        assertThat(configuration.grantTypesSupported()).containsExactly("authorization_code", "refresh_token");
        assertThat(configuration.scopesSupported()).isEmpty();
        assertThat(configuration.codeChallengeMethodsSupported()).isEmpty();
    }

    @Test
    void parseRejectsMissingAuthorizationEndpoint() {
        assertThatThrownBy(() -> client.parse(200, "{\"token_endpoint\":\"http://localhost:9090/oauth/token\"}"))
                .isInstanceOf(OAuth2TokenException.class)
                .hasMessageContaining("authorization_endpoint");
    }

    @Test
    void parseRejectsHttpError() {
        assertThatThrownBy(() -> client.parse(404, "{\"error\":\"not_found\"}"))
                .isInstanceOf(OAuth2TokenException.class)
                .hasMessageContaining("HTTP 404");
    }
}
