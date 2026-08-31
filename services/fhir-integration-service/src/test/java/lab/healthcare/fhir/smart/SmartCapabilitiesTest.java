package lab.healthcare.fhir.smart;

import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class SmartCapabilitiesTest {

    @Test
    void readsDeclaredAuthorizationCodePkceAndScopes() {
        SmartCapabilities capabilities = SmartCapabilities.from(new SmartConfiguration(
                "http://localhost:9090/authorize",
                "http://localhost:9090/oauth/token",
                "http://localhost:9090/",
                List.of("patient/Patient.read", "patient/Observation.read"),
                List.of("code"),
                List.of("authorization_code", "refresh_token"),
                List.of("S256"),
                List.of()));

        assertThat(capabilities.declaresGrantTypes()).isTrue();
        assertThat(capabilities.declaresAuthorizationCode()).isTrue();
        assertThat(capabilities.declaresChallengeMethods()).isTrue();
        assertThat(capabilities.declaresPkceS256()).isTrue();
        assertThat(capabilities.declaresScopes()).isTrue();
        assertThat(capabilities.advertisesScope("patient/Patient.read")).isTrue();
        assertThat(capabilities.advertisesScope("system/Patient.read")).isFalse();
    }

    @Test
    void absentOptionalMetadataIsUndeclaredNotUnsupported() {
        SmartCapabilities capabilities = SmartCapabilities.from(new SmartConfiguration(
                "http://localhost:9090/authorize",
                "http://localhost:9090/oauth/token",
                List.of(),
                List.of(),
                List.of(),
                List.of()));

        assertThat(capabilities.declaresGrantTypes()).isFalse();
        assertThat(capabilities.declaresAuthorizationCode()).isFalse();
        assertThat(capabilities.declaresChallengeMethods()).isFalse();
        assertThat(capabilities.declaresPkceS256()).isFalse();
        assertThat(capabilities.declaresScopes()).isFalse();
        assertThat(capabilities.toString()).doesNotContain("access_token");
        assertThat(capabilities.toString()).doesNotContain("code_verifier");
    }
}
