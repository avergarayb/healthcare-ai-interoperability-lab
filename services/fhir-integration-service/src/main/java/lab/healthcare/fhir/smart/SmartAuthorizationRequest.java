package lab.healthcare.fhir.smart;

import lab.healthcare.fhir.auth.FhirAuthenticationSettings;

import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;

/**
 * One SMART authorization session's public request parameters.
 * {@code aud} comes from the FHIR server profile, not from string-building OAuth URLs.
 * The PKCE verifier stays on {@link AuthorizationSession}, never on this type.
 */
public record SmartAuthorizationRequest(
        String authorizationEndpoint,
        String clientId,
        String redirectUri,
        String scope,
        String state,
        String aud,
        String codeChallenge,
        String codeChallengeMethod) {

    public static final String PKCE_S256 = "S256";

    public SmartAuthorizationRequest {
        requireText(authorizationEndpoint, "authorization endpoint");
        requireText(clientId, "client id");
        requireText(redirectUri, "redirect URI");
        requireText(scope, "scope");
        requireText(state, "state");
        requireText(aud, "aud");
        requireText(codeChallenge, "PKCE code_challenge");
        if (codeChallengeMethod == null || codeChallengeMethod.isBlank()) {
            codeChallengeMethod = PKCE_S256;
        }
        if (!PKCE_S256.equals(codeChallengeMethod)) {
            throw new IllegalArgumentException("PKCE code_challenge_method must be S256");
        }
        authorizationEndpoint = authorizationEndpoint.trim();
        clientId = clientId.trim();
        redirectUri = redirectUri.trim();
        scope = scope.trim();
        state = state.trim();
        aud = aud.trim();
        codeChallenge = codeChallenge.trim();
    }

    public static SmartAuthorizationRequest fromProfile(
            FhirAuthenticationSettings authentication,
            SmartConfiguration configuration,
            String state,
            String codeChallenge) {
        if (authentication == null || !authentication.isSmartAuthorizationCode()) {
            throw new IllegalArgumentException("SMART authorization code settings must be provided");
        }
        if (configuration == null) {
            throw new IllegalArgumentException("SMART configuration must be provided");
        }
        return new SmartAuthorizationRequest(
                configuration.authorizationEndpoint(),
                authentication.clientId(),
                authentication.redirectUri(),
                authentication.scope(),
                state,
                authentication.aud(),
                codeChallenge,
                PKCE_S256);
    }

    public String toAuthorizationUrl() {
        return authorizationEndpoint
                + "?"
                + query(
                        "response_type", "code",
                        "client_id", clientId,
                        "redirect_uri", redirectUri,
                        "scope", scope,
                        "state", state,
                        "aud", aud,
                        "code_challenge", codeChallenge,
                        "code_challenge_method", codeChallengeMethod);
    }

    private static void requireText(String value, String name) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(name + " must be provided");
        }
    }

    private static String query(String... keysAndValues) {
        StringBuilder builder = new StringBuilder();
        for (int index = 0; index < keysAndValues.length; index += 2) {
            if (index > 0) {
                builder.append('&');
            }
            builder.append(encode(keysAndValues[index]))
                    .append('=')
                    .append(encode(keysAndValues[index + 1]));
        }
        return builder.toString();
    }

    private static String encode(String value) {
        return URLEncoder.encode(value == null ? "" : value, StandardCharsets.UTF_8).replace("+", "%20");
    }
}
