package lab.healthcare.fhir.client;

import lab.healthcare.fhir.auth.AccessTokenProvider;
import lab.healthcare.fhir.auth.BearerAccessTokenInterceptor;
import lab.healthcare.fhir.auth.FhirAuthenticationSettings;
import lab.healthcare.fhir.auth.FhirAuthenticationType;
import lab.healthcare.fhir.server.FhirServerProfile;
import lab.healthcare.fhir.server.FhirServerProfileRegistry;
import lab.healthcare.fhir.server.FhirServersProperties;

import ca.uhn.fhir.context.FhirContext;
import ca.uhn.fhir.context.FhirVersionEnum;
import ca.uhn.fhir.rest.client.api.IGenericClient;
import org.junit.jupiter.api.Test;

import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class FhirClientConfigurationTest {

    private final FhirClientConfiguration configuration = new FhirClientConfiguration();
    private final FhirClientFactory factory = new FhirClientFactory();

    @Test
    void fhirContextIsR4ForActiveProfile() {
        FhirServerProfile profile = localHapi();
        FhirContext fhirContext = configuration.fhirContext(factory, profile);

        assertThat(fhirContext.getVersion().getVersion()).isEqualTo(FhirVersionEnum.R4);
    }

    @Test
    void fhirClientUsesActiveProfileBaseUrl() {
        FhirServerProfile profile = localHapi();
        FhirContext fhirContext = configuration.fhirContext(factory, profile);

        IGenericClient client = configuration.fhirClient(factory, fhirContext, profile, AccessTokenProvider.none());

        assertThat(client.getServerBase()).isEqualTo("http://localhost:8080/fhir");
    }

    @Test
    void secondDisabledProfileDoesNotChangeActiveClient() {
        FhirServerProfileRegistry registry = new FhirServerProfileRegistry(twoServers());

        IGenericClient client = factory.createClient(
                factory.createContext(registry.activeProfile()),
                registry.activeProfile());

        assertThat(registry.profiles()).containsKeys("local-hapi", "example-org");
        assertThat(registry.profile("example-org").enabled()).isFalse();
        assertThat(registry.activeProfile().name()).isEqualTo("local-hapi");
        assertThat(client.getServerBase()).isEqualTo("http://localhost:8080/fhir");
    }

    @Test
    void registryRejectsMissingActiveServer() {
        FhirServerProfileRegistry registry = new FhirServerProfileRegistry(
                new FhirServersProperties(" ", Map.of("local-hapi", localSettings())));

        assertThatThrownBy(registry::activeProfile)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("fhir.active-server");
    }

    @Test
    void registryRejectsUnknownProfile() {
        FhirServerProfileRegistry registry = new FhirServerProfileRegistry(
                new FhirServersProperties("missing", Map.of("local-hapi", localSettings())));

        assertThatThrownBy(registry::activeProfile)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("Unknown FHIR server profile");
    }

    @Test
    void registryRejectsDisabledActiveProfile() {
        FhirServerProfileRegistry registry = new FhirServerProfileRegistry(
                new FhirServersProperties("example-org", twoServers().servers()));

        assertThatThrownBy(registry::activeProfile)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("disabled");
    }

    @Test
    void registryRejectsBlankBaseUrl() {
        FhirServerProfileRegistry registry = new FhirServerProfileRegistry(
                new FhirServersProperties(
                        "local-hapi",
                        Map.of("local-hapi", FhirServersProperties.ServerSettings.of(" ", "R4", true, null))));

        assertThatThrownBy(registry::activeProfile)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("base-url");
    }

    @Test
    void registryRejectsMissingFhirVersion() {
        FhirServerProfileRegistry registry = new FhirServerProfileRegistry(
                new FhirServersProperties(
                        "local-hapi",
                        Map.of("local-hapi", FhirServersProperties.ServerSettings.of(
                                "http://localhost:8080/fhir", " ", true, null))));

        assertThatThrownBy(registry::activeProfile)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("fhir-version");
    }

    @Test
    void factoryCreatesR4ContextFromConfiguredVersion() {
        FhirContext context = factory.createContext(localHapi());

        assertThat(factory.fhirVersion(localHapi())).isEqualTo(FhirVersionEnum.R4);
        assertThat(context.getVersion().getVersion()).isEqualTo(FhirVersionEnum.R4);
    }

    @Test
    void factoryRejectsNonR4Version() {
        FhirServerProfile r5 = new FhirServerProfile("future", "http://localhost:8080/fhir", "R5", true);

        assertThatThrownBy(() -> factory.createContext(r5))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("R4");
    }

    @Test
    void factoryRejectsUnknownVersionToken() {
        FhirServerProfile bogus = new FhirServerProfile("bad", "http://localhost:8080/fhir", "DSTU9", true);

        assertThatThrownBy(() -> factory.createContext(bogus))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("unsupported fhir-version");
    }

    @Test
    void factoryRejectsOauthProfileWithoutTokenProvider() {
        FhirServerProfile secured = securedLab();

        assertThatThrownBy(() -> factory.createClient(factory.createContext(secured), secured))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("AccessTokenProvider");
    }

    @Test
    void factoryRegistersBearerInterceptorOnlyForOauthProfiles() {
        FhirContext noneContext = factory.createContext(localHapi());
        IGenericClient noneClient = factory.createClient(noneContext, localHapi(), AccessTokenProvider.none());
        FhirServerProfile secured = securedLab();
        IGenericClient oauthClient = factory.createClient(
                factory.createContext(secured),
                secured,
                () -> "lab-access-token");

        assertThat(noneClient.getInterceptorService().getAllRegisteredInterceptors())
                .noneMatch(interceptor -> interceptor instanceof BearerAccessTokenInterceptor);
        assertThat(oauthClient.getInterceptorService().getAllRegisteredInterceptors())
                .anyMatch(interceptor -> interceptor instanceof BearerAccessTokenInterceptor);
    }

    @Test
    void registryMapsOauthSettingsAndRejectsMissingSecretOnActiveProfile() {
        FhirServerProfileRegistry registry = new FhirServerProfileRegistry(securedServers(""));

        FhirServerProfile disabled = registry.profile("secured-lab");
        assertThat(disabled.enabled()).isFalse();
        assertThat(disabled.authentication().type()).isEqualTo(FhirAuthenticationType.OAUTH2_CLIENT_CREDENTIALS);
        assertThat(disabled.authentication().tokenUrl()).isEqualTo("http://localhost:9090/oauth/token");
        assertThat(disabled.authentication().clientId()).isEqualTo("lab-client");

        FhirServerProfileRegistry enabledWithoutSecret = new FhirServerProfileRegistry(securedServersEnabled(""));
        assertThatThrownBy(enabledWithoutSecret::activeProfile)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("client-secret");
    }

    @Test
    void registryRejectsUnsupportedAuthenticationType() {
        FhirServerProfileRegistry registry = new FhirServerProfileRegistry(
                new FhirServersProperties(
                        "local-hapi",
                        Map.of(
                                "local-hapi",
                                FhirServersProperties.ServerSettings.of(
                                        "http://localhost:8080/fhir",
                                        "R4",
                                        true,
                                        new FhirServersProperties.AuthenticationSettings(
                                                "AUTHORIZATION_CODE", null, null, null, null, null, null, null)))));

        assertThatThrownBy(registry::activeProfile)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("authentication.type");
    }

    @Test
    void registryMapsSmartSettingsWithoutClientSecret() {
        FhirServerProfileRegistry registry = new FhirServerProfileRegistry(
                new FhirServersProperties(
                        "smart-lab",
                        Map.of(
                                "smart-lab",
                                FhirServersProperties.ServerSettings.of(
                                        "http://localhost:8180/fhir",
                                        "R4",
                                        true,
                                        new FhirServersProperties.AuthenticationSettings(
                                                "SMART_AUTHORIZATION_CODE",
                                                null,
                                                "lab-smart-app",
                                                "",
                                                "http://localhost:8180/fhir/.well-known/smart-configuration",
                                                "http://127.0.0.1:8081/smart/callback",
                                                "patient/Patient.read",
                                                "http://localhost:8180/fhir")))));

        FhirServerProfile profile = registry.activeProfile();
        assertThat(profile.authentication().type()).isEqualTo(FhirAuthenticationType.SMART_AUTHORIZATION_CODE);
        assertThat(profile.authentication().aud()).isEqualTo("http://localhost:8180/fhir");
        assertThat(profile.authentication().clientSecret()).isEmpty();
    }

    private static FhirServerProfile localHapi() {
        return new FhirServerProfile("local-hapi", "http://localhost:8080/fhir", "R4", true);
    }

    private static FhirServersProperties.ServerSettings localSettings() {
        return FhirServersProperties.ServerSettings.of("http://localhost:8080/fhir", "R4", true, null);
    }

    private static FhirServersProperties twoServers() {
        return new FhirServersProperties(
                "local-hapi",
                Map.of(
                        "local-hapi", localSettings(),
                        "example-org", FhirServersProperties.ServerSettings.of(
                                "https://example.org/fhir", "R4", false, null)));
    }

    private static FhirServerProfile securedLab() {
        return new FhirServerProfile(
                "secured-lab",
                "http://localhost:8180/fhir",
                "R4",
                true,
                new FhirAuthenticationSettings(
                        FhirAuthenticationType.OAUTH2_CLIENT_CREDENTIALS,
                        "http://localhost:9090/oauth/token",
                        "lab-client",
                        "lab-secret"));
    }

    private static FhirServersProperties securedServers(String secret) {
        return new FhirServersProperties(
                "local-hapi",
                Map.of(
                        "local-hapi", localSettings(),
                        "secured-lab", FhirServersProperties.ServerSettings.of(
                                "http://localhost:8180/fhir",
                                "R4",
                                false,
                                new FhirServersProperties.AuthenticationSettings(
                                        "OAUTH2_CLIENT_CREDENTIALS",
                                        "http://localhost:9090/oauth/token",
                                        "lab-client",
                                        secret,
                                        null,
                                        null,
                                        null,
                                        null))));
    }

    private static FhirServersProperties securedServersEnabled(String secret) {
        return new FhirServersProperties(
                "secured-lab",
                Map.of(
                        "secured-lab",
                        FhirServersProperties.ServerSettings.of(
                                "http://localhost:8180/fhir",
                                "R4",
                                true,
                                new FhirServersProperties.AuthenticationSettings(
                                        "OAUTH2_CLIENT_CREDENTIALS",
                                        "http://localhost:9090/oauth/token",
                                        "lab-client",
                                        secret,
                                        null,
                                        null,
                                        null,
                                        null))));
    }
}
