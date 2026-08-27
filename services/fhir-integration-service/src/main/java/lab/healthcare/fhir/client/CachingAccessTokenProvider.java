package lab.healthcare.fhir.client;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;

public class CachingAccessTokenProvider implements AccessTokenProvider {

    static final Duration EXPIRY_SKEW = Duration.ofSeconds(30);

    private final OAuth2TokenClient tokenClient;
    private final FhirAuthenticationSettings authentication;
    private final Clock clock;
    private AccessToken cached;

    public CachingAccessTokenProvider(
            OAuth2TokenClient tokenClient,
            FhirAuthenticationSettings authentication,
            Clock clock) {
        if (tokenClient == null) {
            throw new IllegalArgumentException("OAuth2 token client must be provided");
        }
        if (authentication == null || !authentication.isClientCredentials()) {
            throw new IllegalArgumentException("OAuth2 client credentials settings must be provided");
        }
        this.tokenClient = tokenClient;
        this.authentication = authentication;
        this.clock = clock == null ? Clock.systemUTC() : clock;
    }

    @Override
    public synchronized String accessToken() {
        Instant now = Instant.now(clock);
        if (cached != null && cached.isUsableAt(now, EXPIRY_SKEW)) {
            return cached.value();
        }
        cached = tokenClient.fetchAccessToken(authentication);
        if (cached == null || cached.value() == null || cached.value().isBlank()) {
            throw new OAuth2TokenException("OAuth token acquisition failed: empty access token");
        }
        return cached.value();
    }
}
