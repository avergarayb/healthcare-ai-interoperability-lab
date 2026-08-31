package lab.healthcare.fhir.smart;

import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class SmartConfigurationValidatorTest {

    private final SmartConfigurationValidator validator = new SmartConfigurationValidator();

    @Test
    void acceptsRequiredEndpointsAndCompatibleDeclaredMetadata() {
        assertThatCode(() -> validator.validate(new SmartConfiguration(
                        "http://localhost:9090/authorize",
                        "http://localhost:9090/oauth/token",
                        null,
                        List.of("patient/Patient.read"),
                        List.of("code"),
                        List.of("authorization_code"),
                        List.of("S256"),
                        List.of())))
                .doesNotThrowAnyException();
    }

    @Test
    void acceptsWhenOptionalListsAreAbsent() {
        assertThatCode(() -> validator.validate(new SmartConfiguration(
                        "http://localhost:9090/authorize",
                        "http://localhost:9090/oauth/token",
                        List.of(),
                        List.of(),
                        List.of(),
                        List.of())))
                .doesNotThrowAnyException();
    }

    @Test
    void rejectsMissingAuthorizationEndpoint() {
        assertThatThrownBy(() -> validator.validate(new SmartConfiguration(
                        null,
                        "http://localhost:9090/oauth/token",
                        List.of(),
                        List.of(),
                        List.of(),
                        List.of())))
                .isInstanceOf(SmartCompatibilityException.class)
                .hasMessageContaining("authorization_endpoint")
                .hasMessageNotContaining("access_token")
                .hasMessageNotContaining("code_verifier");
    }

    @Test
    void rejectsMissingTokenEndpoint() {
        assertThatThrownBy(() -> validator.validate(new SmartConfiguration(
                        "http://localhost:9090/authorize",
                        "  ",
                        List.of(),
                        List.of(),
                        List.of(),
                        List.of())))
                .isInstanceOf(SmartCompatibilityException.class)
                .hasMessageContaining("token_endpoint");
    }

    @Test
    void rejectsDeclaredChallengeMethodsWithoutS256() {
        assertThatThrownBy(() -> validator.validate(new SmartConfiguration(
                        "http://localhost:9090/authorize",
                        "http://localhost:9090/oauth/token",
                        List.of(),
                        List.of("code"),
                        List.of("plain"),
                        List.of())))
                .isInstanceOf(SmartCompatibilityException.class)
                .hasMessageContaining("S256");
    }

    @Test
    void rejectsDeclaredGrantTypesWithoutAuthorizationCode() {
        SmartCompatibilityException exception = org.junit.jupiter.api.Assertions.assertThrows(
                SmartCompatibilityException.class,
                () -> validator.validate(new SmartConfiguration(
                        "http://localhost:9090/authorize",
                        "http://localhost:9090/oauth/token",
                        null,
                        List.of(),
                        List.of("code"),
                        List.of("client_credentials"),
                        List.of("S256"),
                        List.of())));

        assertThat(exception.getMessage()).contains("authorization_code");
        assertThat(exception.getMessage()).doesNotContain("access_token");
    }
}
