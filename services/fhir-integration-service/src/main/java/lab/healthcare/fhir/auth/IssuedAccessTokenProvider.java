package lab.healthcare.fhir.auth;

/**
 * Access token obtained from an interactive SMART callback. No refresh rotation.
 */
public class IssuedAccessTokenProvider implements AccessTokenProvider {

    private final AccessToken token;

    public IssuedAccessTokenProvider(AccessToken token) {
        if (token == null || token.value() == null || token.value().isBlank()) {
            throw new IllegalArgumentException("Issued access token must be provided");
        }
        this.token = token;
    }

    @Override
    public String accessToken() {
        return token.value();
    }

    public AccessToken token() {
        return token;
    }
}
