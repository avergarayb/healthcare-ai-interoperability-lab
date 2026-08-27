package lab.healthcare.fhir.client;

import ca.uhn.fhir.context.FhirContext;
import ca.uhn.fhir.rest.client.api.IGenericClient;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.time.Clock;

@Configuration
@EnableConfigurationProperties(FhirServersProperties.class)
public class FhirClientConfiguration {

    @Bean
    public FhirClientFactory fhirClientFactory() {
        return new FhirClientFactory();
    }

    @Bean
    public FhirServerProfileRegistry fhirServerProfileRegistry(FhirServersProperties properties) {
        return new FhirServerProfileRegistry(properties);
    }

    @Bean
    public FhirServerProfile activeFhirServerProfile(FhirServerProfileRegistry registry) {
        return registry.activeProfile();
    }

    @Bean
    public FhirContext fhirContext(FhirClientFactory factory, FhirServerProfile activeFhirServerProfile) {
        return factory.createContext(activeFhirServerProfile);
    }

    @Bean
    public OAuth2TokenClient oauth2TokenClient() {
        return new OAuth2TokenClient();
    }

    @Bean
    public AccessTokenProvider accessTokenProvider(
            FhirServerProfile activeFhirServerProfile,
            OAuth2TokenClient oauth2TokenClient) {
        FhirAuthenticationSettings authentication = activeFhirServerProfile.authentication();
        if (!authentication.requiresBearerToken()) {
            return AccessTokenProvider.none();
        }
        return new CachingAccessTokenProvider(oauth2TokenClient, authentication, Clock.systemUTC());
    }

    @Bean
    public IGenericClient fhirClient(
            FhirClientFactory factory,
            FhirContext fhirContext,
            FhirServerProfile activeFhirServerProfile,
            AccessTokenProvider accessTokenProvider) {
        return factory.createClient(fhirContext, activeFhirServerProfile, accessTokenProvider);
    }
}
