package lab.healthcare.minihis;

import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.JWSHeader;
import com.nimbusds.jose.crypto.RSASSASigner;
import com.nimbusds.jose.jwk.JWKSet;
import com.nimbusds.jose.jwk.RSAKey;
import com.nimbusds.jose.jwk.gen.RSAKeyGenerator;
import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.SignedJWT;

import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.Date;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class HospitalTokenTest {
    private static final String ISSUER = "http://127.0.0.1:18340/realms/hospital-lab";
    private static final String AUDIENCE = "mini-his-web";

    @Test
    void signedTokenKeepsTheBoundRoleAndRejectsTheNegativeCases() throws Exception {
        RSAKey key = new RSAKeyGenerator(2048).keyID("lab").generate();
        RSAKey other = new RSAKeyGenerator(2048).keyID("other").generate();
        Map<String, HospitalBindings.Binding> bindings = HospitalBindings.load(
                HospitalTokenTest.class.getResourceAsStream("/hospital-bindings.json"));
        Instant now = Instant.now();
        String token = token(key, "revisor.his", "org-mini-his", List.of("clinical-reviewer"), now.plusSeconds(300), ISSUER, AUDIENCE);

        WardPrincipal principal = HospitalTokenVerifier.verify(token, new JWKSet(key.toPublicJWK()), bindings, ISSUER, AUDIENCE, now);
        assertThat(principal.userId()).isEqualTo("revisor.his");
        assertThat(principal.role()).isEqualTo("clinical-reviewer");
        assertThat(principal.organizationId()).isEqualTo("org-mini-his");
        assertThat(principal.sessionMode()).isEqualTo("oidc");
        assertThat(token).doesNotContain(principal.userId() + "secret");

        assertRejected(token(other, "revisor.his", "org-mini-his", List.of("clinical-reviewer"), now.plusSeconds(300), ISSUER, AUDIENCE),
                new JWKSet(key.toPublicJWK()), bindings, now, "invalid_token", 401);
        assertRejected(token(key, "revisor.his", "org-mini-his", List.of("clinical-reviewer"), now.minusSeconds(5), ISSUER, AUDIENCE),
                new JWKSet(key.toPublicJWK()), bindings, now, "invalid_token", 401);
        assertRejected(token(key, "revisor.his", "org-mini-his", List.of("clinical-reviewer"), now.plusSeconds(300), "http://127.0.0.1:9/realms/other", AUDIENCE),
                new JWKSet(key.toPublicJWK()), bindings, now, "invalid_token", 401);
        assertRejected(token(key, "revisor.his", "org-mini-his", List.of("clinical-reviewer"), now.plusSeconds(300), ISSUER, "mini-lis-web"),
                new JWKSet(key.toPublicJWK()), bindings, now, "invalid_token", 401);
        assertRejected(token(key, "revisor.his", "org-pe-lab-demo", List.of("clinical-reviewer"), now.plusSeconds(300), ISSUER, AUDIENCE),
                new JWKSet(key.toPublicJWK()), bindings, now, "organization_denied", 403);
        assertRejected(token(key, "reviewer-pe", "org-pe-lab-demo", List.of("clinical-reviewer"), now.plusSeconds(300), ISSUER, AUDIENCE),
                new JWKSet(key.toPublicJWK()), bindings, now, "organization_denied", 403);
        assertRejected(token(key, "tecnico.lis", "org-mini-his", List.of("lab-technician"), now.plusSeconds(300), ISSUER, AUDIENCE),
                new JWKSet(key.toPublicJWK()), bindings, now, "role_denied", 403);
        assertRejected(token(key, "medico.his", "org-mini-his", List.of("auditor"), now.plusSeconds(300), ISSUER, AUDIENCE),
                new JWKSet(key.toPublicJWK()), bindings, now, "role_denied", 403);
        assertThatThrownBy(() -> HospitalTokenVerifier.verify("not-a-token", new JWKSet(key.toPublicJWK()), bindings, ISSUER, AUDIENCE, now))
                .isInstanceOf(HospitalRejection.class);
    }

    private static void assertRejected(
            String token, JWKSet keys, Map<String, HospitalBindings.Binding> bindings, Instant now, String code, int status) {
        assertThatThrownBy(() -> HospitalTokenVerifier.verify(token, keys, bindings, ISSUER, AUDIENCE, now))
                .isInstanceOf(HospitalRejection.class)
                .extracting(error -> ((HospitalRejection) error).code, error -> ((HospitalRejection) error).status)
                .containsExactly(code, status);
    }

    @Test
    void anIdTokenIsNotForwardedAsAnAccessToken() throws Exception {
        RSAKey key = new RSAKeyGenerator(2048).keyID("lab").generate();
        Instant now = Instant.parse("2026-11-19T12:00:00Z");
        String identity = signed(key, "revisor.his", "mini-his-web", "ID", now.plusSeconds(300));
        String access = signed(key, "revisor.his", "hospital-ai", "Bearer", now.plusSeconds(300));
        assertThat(HospitalTokenVerifier.delegation(identity)).isEmpty();
        assertThat(HospitalTokenVerifier.delegation(access)).isEqualTo(access);
        assertThat(access).doesNotContain("eyJ-secret");
    }

    private static String signed(RSAKey key, String username, String audience, String type, Instant expires) throws Exception {
        JWTClaimsSet claims = new JWTClaimsSet.Builder()
                .issuer(ISSUER)
                .audience(audience)
                .subject("subject-" + username)
                .claim("typ", type)
                .claim("azp", "mini-his-web")
                .claim("preferred_username", username)
                .expirationTime(Date.from(expires))
                .build();
        SignedJWT jwt = new SignedJWT(new JWSHeader.Builder(JWSAlgorithm.RS256).keyID(key.getKeyID()).build(), claims);
        jwt.sign(new RSASSASigner(key));
        return jwt.serialize();
    }

    private static String token(
            RSAKey key, String username, String organization, List<String> roles, Instant expires, String issuer, String audience)
            throws Exception {
        JWTClaimsSet claims = new JWTClaimsSet.Builder()
                .issuer(issuer)
                .audience(audience)
                .subject("subject-" + username)
                .claim("preferred_username", username)
                .claim("organization", organization)
                .claim("realm_access", Map.of("roles", roles))
                .issueTime(Date.from(Instant.now().minusSeconds(30)))
                .expirationTime(Date.from(expires))
                .build();
        SignedJWT jwt = new SignedJWT(new JWSHeader.Builder(JWSAlgorithm.RS256).keyID(key.getKeyID()).build(), claims);
        jwt.sign(new RSASSASigner(key));
        return jwt.serialize();
    }
}
