package lab.healthcare.fhir.smart;

import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class SmartConfigurationTest {

    @Test
    void keepsRequiredEndpointsAndOptionalMetadata() {
        SmartConfiguration configuration = new SmartConfiguration(
                "http://localhost:9090/authorize",
                "http://localhost:9090/oauth/token",
                "http://localhost:9090/",
                List.of("patient/Patient.read"),
                List.of("code"),
                List.of("authorization_code", "refresh_token"),
                List.of("S256"),
                List.of("launch-standalone"));

        assertThat(configuration.authorizationEndpoint()).isEqualTo("http://localhost:9090/authorize");
        assertThat(configuration.tokenEndpoint()).isEqualTo("http://localhost:9090/oauth/token");
        assertThat(configuration.issuer()).isEqualTo("http://localhost:9090/");
        assertThat(configuration.scopesSupported()).containsExactly("patient/Patient.read");
        assertThat(configuration.grantTypesSupported()).contains("authorization_code", "refresh_token");
        assertThat(configuration.codeChallengeMethodsSupported()).containsExactly("S256");
    }

    @Test
    void optionalFieldsStayEmptyWhenAbsent() {
        SmartConfiguration configuration = new SmartConfiguration(
                "http://localhost:9090/authorize",
                "http://localhost:9090/oauth/token",
                List.of(),
                List.of("code"),
                List.of(),
                List.of());

        assertThat(configuration.issuer()).isNull();
        assertThat(configuration.scopesSupported()).isEmpty();
        assertThat(configuration.grantTypesSupported()).isEmpty();
        assertThat(configuration.codeChallengeMethodsSupported()).isEmpty();
    }
}
