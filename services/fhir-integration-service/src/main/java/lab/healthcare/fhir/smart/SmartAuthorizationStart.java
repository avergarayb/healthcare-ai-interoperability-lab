package lab.healthcare.fhir.smart;

import java.time.Instant;
import java.util.List;

/**
 * Public side of one authorize attempt. Safe to show for manual browser navigation.
 */
public record SmartAuthorizationStart(
        String destination,
        String authorizationUrl,
        String state,
        Instant expiresAt,
        List<String> tokenEndpointAuthMethodsSupported) {

    public SmartAuthorizationStart {
        tokenEndpointAuthMethodsSupported = tokenEndpointAuthMethodsSupported == null
                ? List.of()
                : List.copyOf(tokenEndpointAuthMethodsSupported);
    }

    public SmartAuthorizationStart(String destination, String authorizationUrl, String state, Instant expiresAt) {
        this(destination, authorizationUrl, state, expiresAt, List.of());
    }

    public boolean advertisesConfidentialTokenAuth() {
        return SmartTokenExchangeDiagnoser.advertisesConfidentialTokenAuth(tokenEndpointAuthMethodsSupported);
    }

    @Override
    public String toString() {
        return "SmartAuthorizationStart[destination="
                + destination
                + ", hasAuthorizationUrl="
                + (authorizationUrl != null && !authorizationUrl.isBlank())
                + ", hasState="
                + (state != null && !state.isBlank())
                + ", expiresAt="
                + expiresAt
                + ", tokenEndpointAuthMethods="
                + tokenEndpointAuthMethodsSupported
                + "]";
    }
}
