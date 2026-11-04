package lab.healthcare.fhir.iam;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.nimbusds.jose.JOSEObjectType;
import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.JWSHeader;
import com.nimbusds.jose.crypto.RSASSASigner;
import com.nimbusds.jose.jwk.KeyUse;
import com.nimbusds.jose.jwk.RSAKey;
import com.nimbusds.jose.jwk.gen.RSAKeyGenerator;
import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.SignedJWT;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Clock;
import java.time.Instant;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.function.Function;
import org.springframework.security.web.DefaultSecurityFilterChain;
import org.springframework.security.web.FilterChainProxy;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

final class JavaOidcTestSupport {
    static final RSAKey KEY = key("known", 2048);
    static final RSAKey SECOND = key("rotated", 2048);
    static final String SUBJECT = "00000000-0000-4000-8000-000000000202";
    static RSAKey key(String kid, int size) {
        try { return new RSAKeyGenerator(size).keyID(kid).keyUse(KeyUse.SIGNATURE).algorithm(JWSAlgorithm.RS256).generate(); }
        catch (Exception error) { throw new IllegalStateException("synthetic_fixture_key_failed"); }
    }
    static ObjectNode registration() throws Exception {
        var data = (ObjectNode) JavaOidcTrust.JSON.readTree(Files.readAllBytes(Path.of("java-oidc-workload.example.json")));
        data.put("enabled", true);
        return data;
    }
    static JavaOidcTrust trust() throws Exception { return trust(registration()); }
    static JavaOidcTrust trust(JsonNode tree) throws Exception { return JavaOidcTrust.JSON.treeToValue(tree, JavaOidcTrust.class); }
    static Function<String, JsonNode> fetcher(JavaOidcTrust trust, RSAKey key) {
        return url -> {
            var json = JavaOidcTrust.JSON.createObjectNode();
            if (url.equals(trust.discoveryUrl())) {
                json.put("issuer", trust.issuer()).put("jwks_uri", trust.expectedJwksUri())
                    .put("token_endpoint", trust.issuer() + "/protocol/openid-connect/token")
                    .put("authorization_endpoint", trust.issuer() + "/protocol/openid-connect/auth");
            } else { json.putArray("keys").add(JavaOidcTrust.JSON.valueToTree(key.toPublicJWK().toJSONObject())); }
            return json;
        };
    }
    static String token(Map<String, Object> changes) throws Exception { return token(changes, KEY, "known"); }
    static String token(Map<String, Object> changes, RSAKey key, String kid) throws Exception {
        long now = Instant.now().getEpochSecond();
        Map<String, Object> claims = new HashMap<>(Map.of("iss", trust().issuer(), "sub", SUBJECT,
                "aud", JavaOidcTrust.AUDIENCE, "iat", now, "exp", now + 180, "azp", "lab-python-to-java",
                "jti", "synthetic-event", "typ", "Bearer"));
        claims.putAll(changes);
        var jwt = new SignedJWT(new JWSHeader.Builder(JWSAlgorithm.RS256).keyID(kid).type(JOSEObjectType.JWT).build(), JWTClaimsSet.parse(claims));
        jwt.sign(new RSASSASigner(key));
        return jwt.serialize();
    }
    static String signedJson(String payload, ObjectNode header) throws Exception {
        var object = new com.nimbusds.jose.JWSObject(JWSHeader.parse(header.toString()), new com.nimbusds.jose.Payload(payload));
        object.sign("HS256".equals(header.path("alg").asText())
                ? new com.nimbusds.jose.crypto.MACSigner(new byte[32]) : new RSASSASigner(KEY));
        return object.serialize();
    }
    static JavaOidcBoundary boundary(JavaOidcTrust trust, Path audit) {
        var verifier = new JavaWorkloadVerifier(trust, new BoundedOidcKeys(trust, fetcher(trust, KEY), () -> 0L), Clock.systemUTC());
        return new JavaOidcBoundary(trust, verifier, new JavaOidcAudit(audit.toString(), List.of()), Clock.systemUTC());
    }
    static MockMvc mvc(JavaOidcBoundary boundary) {
        return MockMvcBuilders.standaloneSetup(new JavaOidcController())
            .addFilters(new FilterChainProxy(new DefaultSecurityFilterChain(JavaOidcBoundary::matches, boundary))).build();
    }
}
