package lab.healthcare.fhir.client;

import lab.healthcare.fhir.auth.AccessTokenProvider;
import lab.healthcare.fhir.auth.CachingAccessTokenProvider;
import lab.healthcare.fhir.auth.FhirAuthenticationSettings;
import lab.healthcare.fhir.auth.oauth2.OAuth2TokenClient;
import lab.healthcare.fhir.server.FhirServerProfile;
import lab.healthcare.fhir.smart.AuthorizationCodeClient;
import lab.healthcare.fhir.smart.SmartConfigurationClient;
import lab.healthcare.fhir.smart.SmartTokenProvider;

import java.time.Clock;

/**
 * Builds the {@link AccessTokenProvider} that matches a server profile's authentication settings.
 * Used for the active Spring client and for routed destinations.
 */
public class FhirAccessTokenProviders {

    private final OAuth2TokenClient oauth2TokenClient;
    private final SmartConfigurationClient smartConfigurationClient;
    private final AuthorizationCodeClient authorizationCodeClient;
    private final Clock clock;

    public FhirAccessTokenProviders(
            OAuth2TokenClient oauth2TokenClient,
            SmartConfigurationClient smartConfigurationClient,
            AuthorizationCodeClient authorizationCodeClient,
            Clock clock) {
        this.oauth2TokenClient = oauth2TokenClient;
        this.smartConfigurationClient = smartConfigurationClient;
        this.authorizationCodeClient = authorizationCodeClient;
        this.clock = clock == null ? Clock.systemUTC() : clock;
    }

    public AccessTokenProvider forProfile(FhirServerProfile profile) {
        if (profile == null) {
            throw new IllegalArgumentException("FHIR server profile must be provided");
        }
        FhirAuthenticationSettings authentication = profile.authentication();
        if (authentication.isClientCredentials()) {
            return new CachingAccessTokenProvider(oauth2TokenClient, authentication, clock);
        }
        if (authentication.isSmartAuthorizationCode()) {
            return new SmartTokenProvider(
                    smartConfigurationClient, authorizationCodeClient, authentication, clock);
        }
        return AccessTokenProvider.none();
    }
}
