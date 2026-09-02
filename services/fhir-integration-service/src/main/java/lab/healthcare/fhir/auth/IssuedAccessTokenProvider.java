package lab.healthcare.fhir.auth;

import java.time.Duration;
import java.time.Instant;

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

    public boolean isUsableAt(Instant now, Duration skew) {
        return token.isUsableAt(now, skew);
    }

    @Override
    public String toString() {
        return "IssuedAccessTokenProvider[" + token + "]";
    }
}
