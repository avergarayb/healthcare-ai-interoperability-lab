package lab.healthcare.fhir.client;

public record AuthorizationSession(
        String authorizationUrl,
        String state,
        String codeVerifier,
        String codeChallenge) {
}
