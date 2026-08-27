package lab.healthcare.fhir.client;

import java.time.Clock;
import java.time.Instant;

public class SmartTokenProvider implements AccessTokenProvider {

    private final SmartConfigurationClient configurationClient;
    private final AuthorizationCodeClient authorizationCodeClient;
    private final FhirAuthenticationSettings authentication;
    private final Clock clock;
    private SmartConfiguration configuration;
    private AccessToken cached;

    public SmartTokenProvider(
            SmartConfigurationClient configurationClient,
            AuthorizationCodeClient authorizationCodeClient,
            FhirAuthenticationSettings authentication,
            Clock clock) {
        if (configurationClient == null) {
            throw new IllegalArgumentException("SMART configuration client must be provided");
        }
        if (authorizationCodeClient == null) {
            throw new IllegalArgumentException("Authorization code client must be provided");
        }
        if (authentication == null || !authentication.isSmartAuthorizationCode()) {
            throw new IllegalArgumentException("SMART authorization code settings must be provided");
        }
        this.configurationClient = configurationClient;
        this.authorizationCodeClient = authorizationCodeClient;
        this.authentication = authentication;
        this.clock = clock == null ? Clock.systemUTC() : clock;
    }

    @Override
    public synchronized String accessToken() {
        Instant now = Instant.now(clock);
        if (cached != null && cached.isUsableAt(now, CachingAccessTokenProvider.EXPIRY_SKEW)) {
            return cached.value();
        }
        if (cached != null && cached.refreshToken() != null && !cached.refreshToken().isBlank()) {
            cached = authorizationCodeClient.refreshAccessToken(
                    authentication, configuration().tokenEndpoint(), cached.refreshToken());
        } else {
            cached = authorizationCodeClient.authorizeSynthetically(authentication, configuration());
        }
        if (cached == null || cached.value() == null || cached.value().isBlank()) {
            throw new OAuth2TokenException("OAuth token acquisition failed: empty access token");
        }
        return cached.value();
    }

    synchronized AccessToken currentToken() {
        return cached;
    }

    private SmartConfiguration configuration() {
        if (configuration == null) {
            configuration = configurationClient.fetch(authentication.smartConfigurationUrl());
        }
        return configuration;
    }
}
