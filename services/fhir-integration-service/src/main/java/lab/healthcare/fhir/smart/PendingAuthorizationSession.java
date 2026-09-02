package lab.healthcare.fhir.smart;

import java.time.Instant;
import java.util.List;

/**
 * One pending interactive authorize attempt. The verifier is stored only here
 * and is sent solely to the token endpoint.
 */
public record PendingAuthorizationSession(
        String destination,
        String state,
        String codeVerifier,
        String codeChallenge,
        String authorizationUrl,
        String tokenEndpoint,
        String clientId,
        String redirectUri,
        Instant expiresAt,
        List<String> tokenEndpointAuthMethodsSupported) {

    public PendingAuthorizationSession {
        tokenEndpointAuthMethodsSupported = tokenEndpointAuthMethodsSupported == null
                ? List.of()
                : List.copyOf(tokenEndpointAuthMethodsSupported);
    }

    public PendingAuthorizationSession(
            String destination,
            String state,
            String codeVerifier,
            String codeChallenge,
            String authorizationUrl,
            String tokenEndpoint,
            String clientId,
            String redirectUri,
            Instant expiresAt) {
        this(
                destination,
                state,
                codeVerifier,
                codeChallenge,
                authorizationUrl,
                tokenEndpoint,
                clientId,
                redirectUri,
                expiresAt,
                List.of());
    }

    public boolean isExpiredAt(Instant now) {
        return expiresAt == null || now == null || !now.isBefore(expiresAt);
    }

    @Override
    public String toString() {
        return "PendingAuthorizationSession[destination="
                + destination
                + ", hasState="
                + (state != null && !state.isBlank())
                + ", hasCodeVerifier="
                + (codeVerifier != null && !codeVerifier.isBlank())
                + ", hasCodeChallenge="
                + (codeChallenge != null && !codeChallenge.isBlank())
                + ", expiresAt="
                + expiresAt
                + ", tokenEndpointAuthMethods="
                + tokenEndpointAuthMethodsSupported.size()
                + "]";
    }
}
