package lab.healthcare.fhir.client;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class PkceTest {

    @Test
    void rfc7636AppendixBProducesS256Challenge() {
        String verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk";

        assertThat(Pkce.codeChallengeS256(verifier)).isEqualTo("E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM");
    }

    @Test
    void generatedVerifierAndStateAreUrlSafe() {
        String verifier = Pkce.codeVerifier();
        String state = Pkce.newState();

        assertThat(verifier).isNotBlank().doesNotContain("+", "/", "=");
        assertThat(state).isNotBlank().doesNotContain("+", "/", "=");
        assertThat(Pkce.codeChallengeS256(verifier)).isNotBlank();
    }

    @Test
    void blankVerifierIsRejected() {
        assertThatThrownBy(() -> Pkce.codeChallengeS256(" "))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("code_verifier");
    }
}
