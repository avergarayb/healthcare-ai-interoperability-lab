package lab.healthcare.fhir.client;

public record FhirAuthenticationSettings(
        FhirAuthenticationType type,
        String tokenUrl,
        String clientId,
        String clientSecret) {

    public static FhirAuthenticationSettings none() {
        return new FhirAuthenticationSettings(FhirAuthenticationType.NONE, null, null, null);
    }

    public boolean requiresBearerToken() {
        return type == FhirAuthenticationType.OAUTH2_CLIENT_CREDENTIALS;
    }
}
