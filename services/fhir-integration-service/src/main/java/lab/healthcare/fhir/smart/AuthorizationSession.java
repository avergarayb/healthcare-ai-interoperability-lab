package lab.healthcare.fhir.smart;

public record AuthorizationSession(
        String authorizationUrl,
        String state,
        String codeVerifier,
        String codeChallenge) {
}
