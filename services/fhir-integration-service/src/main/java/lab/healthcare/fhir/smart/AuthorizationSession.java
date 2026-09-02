package lab.healthcare.fhir.smart;

public record AuthorizationSession(
        String authorizationUrl,
        String state,
        String codeVerifier,
        String codeChallenge) {

    @Override
    public String toString() {
        return "AuthorizationSession[hasAuthorizationUrl="
                + (authorizationUrl != null && !authorizationUrl.isBlank())
                + ", hasState="
                + (state != null && !state.isBlank())
                + ", hasCodeVerifier="
                + (codeVerifier != null && !codeVerifier.isBlank())
                + ", hasCodeChallenge="
                + (codeChallenge != null && !codeChallenge.isBlank())
                + "]";
    }
}
