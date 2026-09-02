package lab.healthcare.fhir.smart;

import lab.healthcare.fhir.auth.oauth2.OAuth2TokenException;

import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class SmartTokenExchangeDiagnoserTest {

    @Test
    void oracleShapedDiscoveryPlusInvalidClientIsConfidentialClientRequired() {
        SmartTokenExchangeDiagnosis diagnosis = SmartTokenExchangeDiagnoser.fromTokenFailure(
                new OAuth2TokenException(
                        "OAuth token acquisition failed: HTTP 401 invalid_client",
                        401,
                        "invalid_client",
                        null),
                List.of("client_secret_basic", "private_key_jwt"));

        assertThat(diagnosis.tokenIssued()).isFalse();
        assertThat(diagnosis.incompatibility())
                .isEqualTo(SmartTokenAuthenticationIncompatibility.CONFIDENTIAL_CLIENT_REQUIRED);
        assertThat(diagnosis.discoveredTokenEndpointAuthMethods())
                .containsExactly("client_secret_basic", "private_key_jwt");
        assertThat(diagnosis.nextArchitecturalChange()).doesNotContain("client_secret=");
        assertThat(diagnosis.toString()).doesNotContain("access_token");
    }

    @Test
    void errorDescriptionPrivateKeyJwtIsNamedExplicitly() {
        SmartTokenExchangeDiagnosis diagnosis = SmartTokenExchangeDiagnoser.fromTokenFailure(
                new OAuth2TokenException(
                        "OAuth token acquisition failed: HTTP 401 invalid_client",
                        401,
                        "invalid_client",
                        "client authentication private_key_jwt required"),
                List.of("client_secret_basic", "private_key_jwt"));

        assertThat(diagnosis.incompatibility())
                .isEqualTo(SmartTokenAuthenticationIncompatibility.PRIVATE_KEY_JWT);
        assertThat(diagnosis.nextArchitecturalChange()).contains("private_key_jwt");
        assertThat(diagnosis.nextArchitecturalChange()).contains("Do not invent");
    }

    @Test
    void launchScopeWithoutLaunchCodeIsAuthorizationRejected() {
        SmartTokenExchangeDiagnosis diagnosis = SmartTokenExchangeDiagnoser.fromAuthorizationFailure(
                "invalid_request",
                "launch:code-required",
                List.of("client_secret_basic", "private_key_jwt"));

        assertThat(diagnosis.incompatibility())
                .isEqualTo(SmartTokenAuthenticationIncompatibility.AUTHORIZATION_REJECTED);
        assertThat(diagnosis.oauthError()).isEqualTo("invalid_request");
        assertThat(diagnosis.nextArchitecturalChange()).contains("Remove launch");
        assertThat(diagnosis.nextArchitecturalChange()).contains("EHR launch");
        assertThat(diagnosis.toString()).doesNotContain("client_secret=");
    }

    @Test
    void errorDescriptionClientSecretBasicIsNamedExplicitly() {
        SmartTokenExchangeDiagnosis diagnosis = SmartTokenExchangeDiagnoser.fromTokenFailure(
                new OAuth2TokenException(
                        "OAuth token acquisition failed: HTTP 401 invalid_client",
                        401,
                        "invalid_client",
                        "client_secret_basic required"),
                List.of("client_secret_basic", "private_key_jwt"));

        assertThat(diagnosis.incompatibility())
                .isEqualTo(SmartTokenAuthenticationIncompatibility.CLIENT_SECRET_BASIC);
        assertThat(diagnosis.nextArchitecturalChange()).contains("client_secret_basic");
        assertThat(diagnosis.nextArchitecturalChange()).contains("Do not invent a client secret");
    }
}
