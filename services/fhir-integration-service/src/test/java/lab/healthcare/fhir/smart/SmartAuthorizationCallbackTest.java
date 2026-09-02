package lab.healthcare.fhir.smart;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class SmartAuthorizationCallbackTest {

    @Test
    void parsesCodeAndState() {
        SmartAuthorizationCallback callback = SmartAuthorizationCallback.fromRedirect(
                "http://127.0.0.1:8081/smart/callback?code=auth-code-1&state=lab-state");

        assertThat(callback.code()).isEqualTo("auth-code-1");
        assertThat(callback.state()).isEqualTo("lab-state");
        assertThat(callback.toString()).doesNotContain("auth-code-1");
    }

    @Test
    void parseKeepsOAuthErrorWithoutExchanging() {
        SmartAuthorizationCallback callback = SmartAuthorizationCallback.parse(
                "http://localhost:8081/smart/callback?error=access_denied&error_description=user+denied&state=lab-state");

        assertThat(callback.hasOAuthError()).isTrue();
        assertThat(callback.error()).isEqualTo("access_denied");
        assertThat(callback.errorDescription()).isEqualTo("user denied");
        assertThat(callback.toString()).doesNotContain("user denied");
    }

    @Test
    void parseMapsLaunchCodeRequiredWithoutKeepingClientQuery() {
        SmartAuthorizationCallback callback = SmartAuthorizationCallback.parse(
                "http://localhost:8081/smart/callback?error=invalid_request"
                        + "&error_uri=https%3A%2F%2Fexample.test%2Ferrors%2F"
                        + "urn%253Acerner%253Aerror%253Aauthorization-server%253Asmart-v1"
                        + "%253Agrant%253Alaunch%253Acode-required%2Finstances%2Flab"
                        + "&state=lab-state");

        assertThat(callback.error()).isEqualTo("invalid_request");
        assertThat(callback.errorDescription()).isEqualTo("launch:code-required");
        assertThat(callback.toString()).doesNotContain("example.test");
    }

    @Test
    void rejectsMissingCode() {
        assertThatThrownBy(() -> SmartAuthorizationCallback.fromRedirect(
                        "http://127.0.0.1:8081/smart/callback?state=lab-state"))
                .isInstanceOf(SmartAuthorizationException.class)
                .hasMessageContaining("missing authorization code");
    }

    @Test
    void rejectsMissingState() {
        assertThatThrownBy(() -> SmartAuthorizationCallback.fromRedirect(
                        "http://127.0.0.1:8081/smart/callback?code=auth-code-1"))
                .isInstanceOf(SmartAuthorizationException.class)
                .hasMessageContaining("missing state")
                .hasMessageNotContaining("auth-code-1");
    }
}
