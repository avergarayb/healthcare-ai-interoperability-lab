package lab.healthcare.minihis;

import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.jwk.source.ImmutableJWKSet;
import com.nimbusds.jose.proc.JWSVerificationKeySelector;
import com.nimbusds.jose.proc.SecurityContext;
import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.proc.DefaultJWTClaimsVerifier;
import com.nimbusds.jwt.proc.DefaultJWTProcessor;

import java.time.Instant;
import java.util.HashMap;
import java.util.Map;
import java.util.Set;

final class HospitalTokenVerifier {
    private HospitalTokenVerifier() {
    }

    static Map<String, Object> claims(String token, com.nimbusds.jose.jwk.JWKSet keys, String issuer, String audience)
            throws HospitalRejection {
        if (token == null || token.chars().filter(ch -> ch == '.').count() != 2 || token.length() > 4000) {
            throw new HospitalRejection("invalid_token", 401);
        }
        try {
            DefaultJWTProcessor<SecurityContext> processor = new DefaultJWTProcessor<>();
            processor.setJWSKeySelector(new JWSVerificationKeySelector<>(
                    JWSAlgorithm.RS256, new ImmutableJWKSet<>(keys)));
            DefaultJWTClaimsVerifier<SecurityContext> verifier = new DefaultJWTClaimsVerifier<>(
                    new JWTClaimsSet.Builder().issuer(issuer).build(),
                    Set.of("sub", "exp", "iat"));
            verifier.setMaxClockSkew(0);
            processor.setJWTClaimsSetVerifier(verifier);
            JWTClaimsSet set = processor.process(token, null);
            if (set.getAudience() == null || !set.getAudience().contains(audience)) {
                throw new HospitalRejection("invalid_token", 401);
            }
            Map<String, Object> claims = new HashMap<>(set.getClaims());
            claims.put("exp", set.getExpirationTime().toInstant());
            return claims;
        } catch (HospitalRejection ex) {
            throw ex;
        } catch (Exception ex) {
            throw new HospitalRejection("invalid_token", 401);
        }
    }

    static WardPrincipal verify(
            String token, com.nimbusds.jose.jwk.JWKSet keys, Map<String, HospitalBindings.Binding> bindings,
            String issuer, String audience, Instant now) throws HospitalRejection {
        return HospitalIdentity.accept(claims(token, keys, issuer, audience), bindings, issuer, audience, now);
    }
}
