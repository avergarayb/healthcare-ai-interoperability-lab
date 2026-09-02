package lab.healthcare.fhir.smart;

import java.util.List;

/**
 * Metadata published by {@code /.well-known/smart-configuration}.
 * Required endpoints are stored as discovered; optional lists stay empty when absent.
 * Clinical defaults are not invented here.
 */
public record SmartConfiguration(
        String authorizationEndpoint,
        String tokenEndpoint,
        String issuer,
        List<String> scopesSupported,
        List<String> responseTypesSupported,
        List<String> grantTypesSupported,
        List<String> codeChallengeMethodsSupported,
        List<String> capabilities,
        List<String> tokenEndpointAuthMethodsSupported) {

    public SmartConfiguration {
        issuer = blankToNull(issuer);
        scopesSupported = copy(scopesSupported);
        responseTypesSupported = copy(responseTypesSupported);
        grantTypesSupported = copy(grantTypesSupported);
        codeChallengeMethodsSupported = copy(codeChallengeMethodsSupported);
        capabilities = copy(capabilities);
        tokenEndpointAuthMethodsSupported = copy(tokenEndpointAuthMethodsSupported);
    }

    public SmartConfiguration(
            String authorizationEndpoint,
            String tokenEndpoint,
            String issuer,
            List<String> scopesSupported,
            List<String> responseTypesSupported,
            List<String> grantTypesSupported,
            List<String> codeChallengeMethodsSupported,
            List<String> capabilities) {
        this(
                authorizationEndpoint,
                tokenEndpoint,
                issuer,
                scopesSupported,
                responseTypesSupported,
                grantTypesSupported,
                codeChallengeMethodsSupported,
                capabilities,
                List.of());
    }

    public SmartConfiguration(
            String authorizationEndpoint,
            String tokenEndpoint,
            List<String> scopesSupported,
            List<String> responseTypesSupported,
            List<String> codeChallengeMethodsSupported,
            List<String> capabilities) {
        this(
                authorizationEndpoint,
                tokenEndpoint,
                null,
                scopesSupported,
                responseTypesSupported,
                List.of(),
                codeChallengeMethodsSupported,
                capabilities,
                List.of());
    }

    public SmartCapabilities interpretedCapabilities() {
        return SmartCapabilities.from(this);
    }

    private static String blankToNull(String value) {
        return value == null || value.isBlank() ? null : value.trim();
    }

    private static List<String> copy(List<String> values) {
        return values == null ? List.of() : List.copyOf(values);
    }
}
