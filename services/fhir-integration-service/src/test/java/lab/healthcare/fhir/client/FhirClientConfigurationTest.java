package lab.healthcare.fhir.client;

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

        IGenericClient client = configuration.fhirClient(factory, fhirContext, profile);

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
                        Map.of("local-hapi", new FhirServersProperties.ServerSettings(" ", "R4", true))));

        assertThatThrownBy(registry::activeProfile)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("base-url");
    }

    @Test
    void registryRejectsMissingFhirVersion() {
        FhirServerProfileRegistry registry = new FhirServerProfileRegistry(
                new FhirServersProperties(
                        "local-hapi",
                        Map.of("local-hapi", new FhirServersProperties.ServerSettings(
                                "http://localhost:8080/fhir", " ", true))));

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

    private static FhirServerProfile localHapi() {
        return new FhirServerProfile("local-hapi", "http://localhost:8080/fhir", "R4", true);
    }

    private static FhirServersProperties.ServerSettings localSettings() {
        return new FhirServersProperties.ServerSettings("http://localhost:8080/fhir", "R4", true);
    }

    private static FhirServersProperties twoServers() {
        return new FhirServersProperties(
                "local-hapi",
                Map.of(
                        "local-hapi", localSettings(),
                        "example-org", new FhirServersProperties.ServerSettings(
                                "https://example.org/fhir", "R4", false)));
    }
}
