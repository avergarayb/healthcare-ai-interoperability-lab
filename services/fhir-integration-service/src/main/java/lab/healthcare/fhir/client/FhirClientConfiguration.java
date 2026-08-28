package lab.healthcare.fhir.client;

import lab.healthcare.fhir.auth.AccessTokenProvider;
import lab.healthcare.fhir.auth.oauth2.OAuth2TokenClient;
import lab.healthcare.fhir.server.FhirServerProfile;
import lab.healthcare.fhir.server.FhirServerProfileRegistry;
import lab.healthcare.fhir.server.FhirServersProperties;
import lab.healthcare.fhir.smart.AuthorizationCodeClient;
import lab.healthcare.fhir.smart.SmartConfigurationClient;

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
    public SmartConfigurationClient smartConfigurationClient() {
        return new SmartConfigurationClient();
    }

    @Bean
    public AuthorizationCodeClient authorizationCodeClient() {
        return new AuthorizationCodeClient();
    }

    @Bean
    public FhirAccessTokenProviders fhirAccessTokenProviders(
            OAuth2TokenClient oauth2TokenClient,
            SmartConfigurationClient smartConfigurationClient,
            AuthorizationCodeClient authorizationCodeClient) {
        return new FhirAccessTokenProviders(
                oauth2TokenClient, smartConfigurationClient, authorizationCodeClient, Clock.systemUTC());
    }

    @Bean
    public AccessTokenProvider accessTokenProvider(
            FhirServerProfile activeFhirServerProfile,
            FhirAccessTokenProviders fhirAccessTokenProviders) {
        return fhirAccessTokenProviders.forProfile(activeFhirServerProfile);
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
