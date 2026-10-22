package lab.healthcare.fhir.interop;

import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class SourceRegistryTest {

    @Test
    void aDeclaredSystemIsListedWithoutInstallingAConnector() {
        InteropSourcesProperties properties = new InteropSourcesProperties();
        properties.setSources(Map.of(
                "mini-lis", source("org-mini-lis", "Mini LIS", List.of("patient", "observation")),
                "clinic-d", source("org-clinic-d", "Clinic D", List.of("patient", "service-request"))));
        SourceRegistry registry = new SourceRegistry(properties);
        assertThat(registry.sources()).extracting(SourceRegistry.SourceDescriptor::key)
                .containsExactlyInAnyOrder("mini-lis", "clinic-d");
        assertThat(registry.sources())
                .filteredOn(source -> "clinic-d".equals(source.key()))
                .singleElement()
                .extracting(SourceRegistry.SourceDescriptor::organizationId)
                .isEqualTo("org-clinic-d");
    }

    @Test
    void anUnknownCapabilityFailsStartup() {
        InteropSourcesProperties properties = new InteropSourcesProperties();
        properties.setSources(Map.of("clinic-d", source("org-clinic-d", "Clinic D", List.of("soap"))));
        assertThatThrownBy(() -> new SourceRegistry(properties))
                .isInstanceOf(IllegalStateException.class);
    }

    private static InteropSourcesProperties.SourceProperties source(
            String organizationId, String displayName, List<String> capabilities) {
        InteropSourcesProperties.SourceProperties properties = new InteropSourcesProperties.SourceProperties();
        properties.setOrganizationId(organizationId);
        properties.setDisplayName(displayName);
        properties.setBaseUrl("http://127.0.0.1:9");
        properties.setCapabilities(capabilities);
        return properties;
    }
}
