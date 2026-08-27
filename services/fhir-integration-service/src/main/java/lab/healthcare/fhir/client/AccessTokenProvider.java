package lab.healthcare.fhir.client;

public interface AccessTokenProvider {

    String accessToken();

    static AccessTokenProvider none() {
        return () -> {
            throw new IllegalStateException("No OAuth2 token provider is configured");
        };
    }
}
