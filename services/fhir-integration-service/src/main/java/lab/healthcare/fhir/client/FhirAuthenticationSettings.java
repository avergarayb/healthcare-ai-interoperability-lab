package lab.healthcare.fhir.client;

public record FhirAuthenticationSettings(
        FhirAuthenticationType type,
        String tokenUrl,
        String clientId,
        String clientSecret,
        String smartConfigurationUrl,
        String redirectUri,
        String scope,
        String aud) {

    public FhirAuthenticationSettings(
            FhirAuthenticationType type,
            String tokenUrl,
            String clientId,
            String clientSecret) {
        this(type, tokenUrl, clientId, clientSecret, null, null, null, null);
    }

    public static FhirAuthenticationSettings none() {
        return new FhirAuthenticationSettings(FhirAuthenticationType.NONE, null, null, null, null, null, null, null);
    }

    public boolean requiresBearerToken() {
        return type == FhirAuthenticationType.OAUTH2_CLIENT_CREDENTIALS
                || type == FhirAuthenticationType.SMART_AUTHORIZATION_CODE;
    }

    public boolean isClientCredentials() {
        return type == FhirAuthenticationType.OAUTH2_CLIENT_CREDENTIALS;
    }

    public boolean isSmartAuthorizationCode() {
        return type == FhirAuthenticationType.SMART_AUTHORIZATION_CODE;
    }
}
