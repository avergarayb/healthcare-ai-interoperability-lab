package lab.healthcare.fhir.smart;

import lab.healthcare.fhir.auth.FhirAuthenticationSettings;
import lab.healthcare.fhir.auth.FhirAuthenticationType;

import org.junit.jupiter.api.Test;

import java.net.URI;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class SmartAuthorizationRequestTest {

    @Test
    void copiesAudScopesRedirectAndPkceFromProfile() {
        String challenge = Pkce.codeChallengeS256("lab-pkce-verifier");
        SmartAuthorizationRequest request = SmartAuthorizationRequest.fromProfile(
                smartSettings(),
                configuration(),
                "lab-state",
                challenge);

        assertThat(request.aud()).isEqualTo("http://localhost:8180/fhir");
        assertThat(request.state()).isEqualTo("lab-state");
        assertThat(request.redirectUri()).isEqualTo("http://127.0.0.1:8081/smart/callback");
        assertThat(request.scope()).isEqualTo("patient/Patient.read patient/Observation.read");
        assertThat(request.codeChallenge()).isEqualTo(challenge);
        assertThat(request.codeChallengeMethod()).isEqualTo(SmartAuthorizationRequest.PKCE_S256);
        assertThat(request.toString()).doesNotContain("client_secret");
        assertThat(request.toString()).doesNotContain("code_verifier");
        assertThat(request.toString()).doesNotContain("access_token");

        URI uri = URI.create(request.toAuthorizationUrl());
        assertThat(uri.getPath()).isEqualTo("/authorize");
        assertThat(uri.getRawQuery()).contains("aud=http%3A%2F%2Flocalhost%3A8180%2Ffhir");
        assertThat(uri.getRawQuery()).contains("code_challenge_method=S256");
    }

    @Test
    void rejectsNonS256ChallengeMethod() {
        assertThatThrownBy(() -> new SmartAuthorizationRequest(
                        "http://localhost:9090/authorize",
                        "lab-smart-app",
                        "http://127.0.0.1:8081/smart/callback",
                        "patient/Patient.read",
                        "lab-state",
                        "http://localhost:8180/fhir",
                        "challenge",
                        "plain"))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("S256");
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
                List.of());
    }
}
