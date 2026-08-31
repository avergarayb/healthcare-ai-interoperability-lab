package lab.healthcare.fhir.smart;

import java.util.List;

/**
 * Interpretation of discovered SMART metadata. Does not replace {@link SmartConfiguration}.
 * Absent optional lists mean "undeclared", not "unsupported".
 */
public record SmartCapabilities(
        boolean declaresGrantTypes,
        boolean declaresAuthorizationCode,
        boolean declaresChallengeMethods,
        boolean declaresPkceS256,
        boolean declaresScopes,
        List<String> scopesSupported,
        List<String> grantTypesSupported,
        List<String> codeChallengeMethodsSupported) {

    public SmartCapabilities {
        scopesSupported = copy(scopesSupported);
        grantTypesSupported = copy(grantTypesSupported);
        codeChallengeMethodsSupported = copy(codeChallengeMethodsSupported);
    }

    public static SmartCapabilities from(SmartConfiguration configuration) {
        if (configuration == null) {
            throw new IllegalArgumentException("SMART configuration must be provided");
        }
        List<String> grants = configuration.grantTypesSupported();
        List<String> methods = configuration.codeChallengeMethodsSupported();
        List<String> scopes = configuration.scopesSupported();
        return new SmartCapabilities(
                !grants.isEmpty(),
                containsIgnoreCase(grants, "authorization_code"),
                !methods.isEmpty(),
                containsIgnoreCase(methods, "S256"),
                !scopes.isEmpty(),
                scopes,
                grants,
                methods);
    }

    public boolean advertisesScope(String scope) {
        return containsIgnoreCase(scopesSupported, scope);
    }

    private static boolean containsIgnoreCase(List<String> values, String expected) {
        if (expected == null || expected.isBlank()) {
            return false;
        }
        String needle = expected.trim();
        for (String value : values) {
            if (value != null && needle.equalsIgnoreCase(value.trim())) {
                return true;
            }
        }
        return false;
    }

    private static List<String> copy(List<String> values) {
        return values == null ? List.of() : List.copyOf(values);
    }

    @Override
    public String toString() {
        return "SmartCapabilities[declaresGrantTypes="
                + declaresGrantTypes
                + ", declaresAuthorizationCode="
                + declaresAuthorizationCode
                + ", declaresChallengeMethods="
                + declaresChallengeMethods
                + ", declaresPkceS256="
                + declaresPkceS256
                + ", declaresScopes="
                + declaresScopes
                + ", scopesSupported="
                + scopesSupported.size()
                + ", grantTypesSupported="
                + grantTypesSupported.size()
                + ", codeChallengeMethodsSupported="
                + codeChallengeMethodsSupported.size()
                + "]";
    }
}
