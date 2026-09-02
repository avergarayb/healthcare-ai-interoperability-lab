package lab.healthcare.fhir.smart;

import java.util.List;

/**
 * Safe explanation of a SMART token-exchange attempt. Never includes tokens,
 * codes, verifiers, or secrets.
 */
public record SmartTokenExchangeDiagnosis(
        boolean tokenIssued,
        boolean publicPkceAttempted,
        SmartTokenAuthenticationIncompatibility incompatibility,
        List<String> discoveredTokenEndpointAuthMethods,
        String oauthError,
        int httpStatus,
        String nextArchitecturalChange,
        String detail) {

    public SmartTokenExchangeDiagnosis {
        if (incompatibility == null) {
            incompatibility = SmartTokenAuthenticationIncompatibility.NONE;
        }
        discoveredTokenEndpointAuthMethods = discoveredTokenEndpointAuthMethods == null
                ? List.of()
                : List.copyOf(discoveredTokenEndpointAuthMethods);
        oauthError = blankToNull(oauthError);
        nextArchitecturalChange = SmartAuthorizationException.requireSafe(
                nextArchitecturalChange == null || nextArchitecturalChange.isBlank()
                        ? "none"
                        : nextArchitecturalChange);
        detail = SmartAuthorizationException.requireSafe(
                detail == null || detail.isBlank() ? incompatibility.name() : detail);
    }

    public static SmartTokenExchangeDiagnosis issued(List<String> discoveredTokenEndpointAuthMethods) {
        return new SmartTokenExchangeDiagnosis(
                true,
                true,
                SmartTokenAuthenticationIncompatibility.NONE,
                discoveredTokenEndpointAuthMethods,
                null,
                200,
                "none",
                "Token exchange succeeded with public PKCE");
    }

    @Override
    public String toString() {
        return "SmartTokenExchangeDiagnosis[tokenIssued="
                + tokenIssued
                + ", publicPkceAttempted="
                + publicPkceAttempted
                + ", incompatibility="
                + incompatibility
                + ", discoveredTokenEndpointAuthMethods="
                + discoveredTokenEndpointAuthMethods
                + ", oauthError="
                + oauthError
                + ", httpStatus="
                + httpStatus
                + ", nextArchitecturalChange="
                + nextArchitecturalChange
                + ", detail="
                + detail
                + "]";
    }

    private static String blankToNull(String value) {
        return value == null || value.isBlank() ? null : value.trim();
    }
}
