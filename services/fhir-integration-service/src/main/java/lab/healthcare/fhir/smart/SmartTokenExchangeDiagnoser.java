package lab.healthcare.fhir.smart;

import lab.healthcare.fhir.auth.oauth2.OAuth2TokenException;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/**
 * Interprets token-endpoint rejection against discovered
 * {@code token_endpoint_auth_methods_supported}. Does not implement confidential
 * client authentication.
 */
public final class SmartTokenExchangeDiagnoser {

    private SmartTokenExchangeDiagnoser() {
    }

    public static SmartTokenExchangeDiagnosis fromTokenFailure(
            OAuth2TokenException exception, List<String> discoveredTokenEndpointAuthMethods) {
        List<String> methods = normalized(discoveredTokenEndpointAuthMethods);
        String error = exception == null ? null : exception.error();
        String description = exception == null ? null : exception.errorDescription();
        int status = exception == null ? 0 : exception.httpStatus();
        String combined = ((error == null ? "" : error) + " " + (description == null ? "" : description))
                .toLowerCase(Locale.ROOT);

        if (mentionsPrivateKeyJwt(combined, methods)) {
            return diagnosis(
                    SmartTokenAuthenticationIncompatibility.PRIVATE_KEY_JWT,
                    methods,
                    error,
                    status,
                    "A later task must implement private_key_jwt (JWT client assertion) if the Oracle app is registered as confidential-asymmetric. Do not invent a JWT or private key.",
                    "Token endpoint rejected public PKCE. Discovery/error indicate private_key_jwt");
        }
        if (mentionsClientSecret(combined, methods)) {
            return diagnosis(
                    SmartTokenAuthenticationIncompatibility.CLIENT_SECRET_BASIC,
                    methods,
                    error,
                    status,
                    "A later task must implement client_secret_basic only if the Oracle app is registered with a client secret. Do not invent a client secret.",
                    "Token endpoint rejected public PKCE. Discovery/error indicate client_secret_basic");
        }
        if (declaresConfidentialOnly(methods)) {
            return diagnosis(
                    SmartTokenAuthenticationIncompatibility.CONFIDENTIAL_CLIENT_REQUIRED,
                    methods,
                    error,
                    status,
                    "Confirm which confidential method the Oracle application registration actually uses (client_secret_basic or private_key_jwt), then implement that mode. Public PKCE is not sufficient for this token endpoint advertisement.",
                    "Discovered token_endpoint_auth_methods_supported does not include none");
        }
        return diagnosis(
                SmartTokenAuthenticationIncompatibility.TOKEN_ENDPOINT_REJECTED,
                methods,
                error,
                status,
                "Inspect the OAuth error code and the registered Oracle application type. Do not add a fabricated secret.",
                "Token endpoint rejected the authorization-code exchange");
    }

    public static SmartTokenExchangeDiagnosis fromAuthorizationFailure(
            String oauthError, List<String> discoveredTokenEndpointAuthMethods) {
        return fromAuthorizationFailure(oauthError, null, discoveredTokenEndpointAuthMethods);
    }

    public static SmartTokenExchangeDiagnosis fromAuthorizationFailure(
            String oauthError, String errorHint, List<String> discoveredTokenEndpointAuthMethods) {
        String hint = errorHint == null ? "" : errorHint.toLowerCase(Locale.ROOT);
        if (hint.contains("launch") && hint.contains("code-required")) {
            return new SmartTokenExchangeDiagnosis(
                    false,
                    true,
                    SmartTokenAuthenticationIncompatibility.AUTHORIZATION_REJECTED,
                    discoveredTokenEndpointAuthMethods,
                    oauthError,
                    0,
                    "Standalone SMART must not request the launch scope without a launch code. Remove launch from the sandbox scope and retry. EHR launch remains out of scope.",
                    "Authorization server rejected launch without a launch code");
        }
        return new SmartTokenExchangeDiagnosis(
                false,
                true,
                SmartTokenAuthenticationIncompatibility.AUTHORIZATION_REJECTED,
                discoveredTokenEndpointAuthMethods,
                oauthError,
                0,
                "Fix the authorization request (scope, redirect URI, or user consent). Token exchange was not attempted.",
                "Authorization server returned an OAuth error before token exchange");
    }

    public static boolean advertisesConfidentialTokenAuth(List<String> discoveredTokenEndpointAuthMethods) {
        return declaresConfidentialOnly(normalized(discoveredTokenEndpointAuthMethods));
    }

    private static SmartTokenExchangeDiagnosis diagnosis(
            SmartTokenAuthenticationIncompatibility incompatibility,
            List<String> methods,
            String error,
            int status,
            String next,
            String detail) {
        return new SmartTokenExchangeDiagnosis(
                false, true, incompatibility, methods, error, status, next, detail);
    }

    private static boolean declaresConfidentialOnly(List<String> methods) {
        if (methods.isEmpty()) {
            return false;
        }
        boolean confidential = methods.contains("client_secret_basic")
                || methods.contains("client_secret_post")
                || methods.contains("private_key_jwt");
        return confidential && !methods.contains("none");
    }

    private static boolean mentionsPrivateKeyJwt(String combined, List<String> methods) {
        return combined.contains("private_key_jwt")
                || combined.contains("client_assertion")
                || combined.contains("jwt-bearer")
                || (combined.contains("invalid_client") && methods.equals(List.of("private_key_jwt")));
    }

    private static boolean mentionsClientSecret(String combined, List<String> methods) {
        return combined.contains("client_secret_basic")
                || combined.contains("client_secret_post")
                || combined.contains("client_secret")
                || (combined.contains("invalid_client")
                        && methods.contains("client_secret_basic")
                        && !methods.contains("private_key_jwt"));
    }

    private static List<String> normalized(List<String> values) {
        if (values == null || values.isEmpty()) {
            return List.of();
        }
        List<String> normalized = new ArrayList<>();
        for (String value : values) {
            if (value != null && !value.isBlank()) {
                normalized.add(value.trim().toLowerCase(Locale.ROOT));
            }
        }
        return List.copyOf(normalized);
    }
}
