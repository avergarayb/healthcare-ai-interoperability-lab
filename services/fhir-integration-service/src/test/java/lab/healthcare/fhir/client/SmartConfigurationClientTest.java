package lab.healthcare.fhir.client;

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
        assertThat(configuration.scopesSupported()).contains("patient/Patient.read", "patient/Observation.read");
        assertThat(configuration.responseTypesSupported()).containsExactly("code");
        assertThat(configuration.codeChallengeMethodsSupported()).containsExactly("S256");
        assertThat(configuration.capabilities()).contains("launch-standalone", "client-public");
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
