package lab.healthcare.fhir.iam;

import com.fasterxml.jackson.databind.JsonNode;
import com.nimbusds.jose.JOSEObjectType;
import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.proc.DefaultJOSEObjectTypeVerifier;
import com.nimbusds.jose.proc.SecurityContext;
import com.nimbusds.jwt.proc.DefaultJWTProcessor;
import java.time.Clock;
import java.time.Instant;
import java.util.Base64;
import java.util.List;
import org.springframework.security.oauth2.core.OAuth2Error;
import org.springframework.security.oauth2.core.OAuth2TokenValidator;
import org.springframework.security.oauth2.core.OAuth2TokenValidatorResult;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.JwtException;
import org.springframework.security.oauth2.jwt.JwtValidationException;
import org.springframework.security.oauth2.jwt.NimbusJwtDecoder;
import org.springframework.security.oauth2.server.resource.authentication.BearerTokenAuthenticationToken;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationProvider;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;

/** Nimbus verifies signatures; explicit Spring validator/profile supplies resource policy. */
final class JavaWorkloadVerifier {
    record Verified(String subject, String clientId, Instant expiresAt) {
        @Override public String toString() { return "Verified[redacted]"; }
    }
    private final JavaOidcTrust trust;
    private final JwtAuthenticationProvider provider;
    private final Clock clock;
    JavaWorkloadVerifier(JavaOidcTrust trust, BoundedOidcKeys keys, Clock clock) {
        this.trust = trust; this.clock = clock;
        var processor = new DefaultJWTProcessor<SecurityContext>();
        processor.setJWSTypeVerifier(new DefaultJOSEObjectTypeVerifier<>(new JOSEObjectType("JWT"), new JOSEObjectType("at+jwt")));
        processor.setJWSKeySelector((header, context) -> {
            if (!JWSAlgorithm.RS256.equals(header.getAlgorithm())) { throw new JavaOidcFailure("algorithm_rejected", 401); }
            return keys.select(header.getKeyID());
        });
        // Timestamp/issuer/audience validation is explicit below, not Nimbus's default skew.
        processor.setJWTClaimsSetVerifier((claims, context) -> { });
        var decoder = new NimbusJwtDecoder(processor);
        OAuth2TokenValidator<Jwt> validator = jwt -> {
            String reason = validate(jwt);
            return reason == null ? OAuth2TokenValidatorResult.success()
                    : OAuth2TokenValidatorResult.failure(new OAuth2Error("invalid_token", reason, null));
        };
        decoder.setJwtValidator(validator);
        provider = new JwtAuthenticationProvider(encoded -> {
            strictEnvelope(encoded);
            try { return decoder.decode(encoded); }
            catch (JwtValidationException invalid) {
                throw new JavaOidcFailure(invalid.getErrors().iterator().next().getDescription(), 401);
            } catch (JwtException invalid) {
                for (Throwable cause = invalid; cause != null; cause = cause.getCause()) {
                    if (cause instanceof JavaOidcFailure failure) { throw failure; }
                }
                throw new JavaOidcFailure("verification_rejected", 401);
            }
        });
        // Never turn JWT scopes/groups into SCOPE_* or local application grants.
        provider.setJwtAuthenticationConverter(jwt -> new JwtAuthenticationToken(jwt, List.of()));
    }
    Verified verify(String token) {
        if (!trust.enabled()) { throw new JavaOidcFailure("provider_disabled", 503); }
        JwtAuthenticationToken authenticated = (JwtAuthenticationToken) provider.authenticate(new BearerTokenAuthenticationToken(token));
        Jwt jwt = authenticated.getToken();
        return new Verified(jwt.getSubject(), jwt.getClaimAsString("azp"), jwt.getExpiresAt());
    }
    private String validate(Jwt jwt) {
        if (!trust.issuer().equals(jwt.getClaimAsString("iss"))) { return "issuer_rejected"; }
        if (!List.of(JavaOidcTrust.AUDIENCE).equals(jwt.getAudience())) { return "audience_rejected"; }
        Instant now = clock.instant(), issued = jwt.getIssuedAt(), expires = jwt.getExpiresAt();
        if (expires == null || !expires.isAfter(now)) { return "token_expired"; }
        if (issued == null || issued.isAfter(now.plusSeconds(trust.clockSkewSeconds()))
                || !expires.isAfter(issued)
                || java.time.Duration.between(issued, expires).getSeconds() > trust.maxAccessTokenLifetimeSeconds()
                || (jwt.getNotBefore() != null && jwt.getNotBefore().isAfter(now.plusSeconds(trust.clockSkewSeconds())))) {
            return "time_rejected";
        }
        if (!"Bearer".equals(jwt.getClaimAsString("typ"))) { return "purpose_rejected"; }
        if (!bounded(jwt.getSubject(), 512) || !bounded(jwt.getClaimAsString("azp"), 128)
                || !bounded(jwt.getClaimAsString("jti"), 256)) { return "verification_rejected"; }
        return null;
    }
    private static boolean bounded(String value, int max) { return value != null && !value.isEmpty() && value.length() <= max; }
    private void strictEnvelope(String token) {
        try {
            if (token.length() > 16384 || !token.matches("[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+")) {
                throw new JavaOidcFailure("credential_malformed", 401);
            }
            String[] parts = token.split("\\.");
            JsonNode header = JavaOidcTrust.JSON.readTree(Base64.getUrlDecoder().decode(parts[0]));
            JsonNode claims = JavaOidcTrust.JSON.readTree(Base64.getUrlDecoder().decode(parts[1]));
            if (!header.isObject() || !claims.isObject()) { throw new JavaOidcFailure("verification_rejected", 401); }
            if (!"RS256".equals(header.path("alg").asText()) || !List.of("JWT", "at+jwt").contains(header.path("typ").asText())) {
                throw new JavaOidcFailure("algorithm_rejected", 401);
            }
            for (String field : List.of("jku", "x5u", "jwk", "x5c", "crit")) {
                if (header.has(field)) { throw new JavaOidcFailure("key_source_rejected", 401); }
            }
            if (!header.path("kid").isTextual() || !header.get("kid").asText().matches("[A-Za-z0-9_.-]{1,128}")) {
                throw new JavaOidcFailure("unknown_key", 401);
            }
            for (String field : List.of("iss", "sub", "azp", "jti", "typ")) {
                if (!claims.path(field).isTextual()) { throw new JavaOidcFailure("verification_rejected", 401); }
            }
            for (String field : List.of("iat", "exp", "nbf")) {
                if ((claims.has(field) || !field.equals("nbf")) && (!claims.path(field).isIntegralNumber()
                        || !claims.path(field).canConvertToLong() || claims.path(field).longValue() < 0)) {
                    throw new JavaOidcFailure("time_rejected", 401);
                }
            }
            // Reject on original integers before Nimbus converts seconds to Date milliseconds.
            // A signed out-of-range NumericDate must not wrap into a plausible current Instant.
            long now = clock.instant().getEpochSecond();
            long issued = claims.get("iat").longValue(), expires = claims.get("exp").longValue();
            if (expires <= now) { throw new JavaOidcFailure("token_expired", 401); }
            // Both integers are nonnegative, so subtraction after ordering cannot overflow.
            if (issued > now + trust.clockSkewSeconds() || expires <= issued
                    || expires - issued > trust.maxAccessTokenLifetimeSeconds()
                    || (claims.has("nbf") && claims.get("nbf").longValue() > now + trust.clockSkewSeconds())) {
                throw new JavaOidcFailure("time_rejected", 401);
            }
        } catch (JavaOidcFailure failure) { throw failure; }
        catch (Exception invalid) { throw new JavaOidcFailure("verification_rejected", 401); }
    }
}
