package lab.healthcare.fhir.capability;

import org.junit.jupiter.api.Test;

import java.util.Map;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;

class FhirServerCapabilitiesTest {

    private final FhirServerCapabilities capabilities = new FhirServerCapabilities(
            "local-hapi",
            "4.0.1",
            "HAPI FHIR Server",
            "http://localhost:8080/fhir",
            Map.of(
                    "Patient",
                    new FhirResourceCapabilities("Patient", Set.of(FhirInteraction.READ, FhirInteraction.SEARCH_TYPE)),
                    "Observation",
                    new FhirResourceCapabilities("Observation", Set.of(FhirInteraction.READ))));

    @Test
    void supportsResourceAndInteractionQueries() {
        assertThat(capabilities.supportsResource("Patient")).isTrue();
        assertThat(capabilities.supports("Patient", FhirInteraction.READ)).isTrue();
        assertThat(capabilities.supports("Patient", FhirInteraction.SEARCH_TYPE)).isTrue();
        assertThat(capabilities.destination()).isEqualTo("local-hapi");
        assertThat(capabilities.fhirVersion()).isEqualTo("4.0.1");
    }

    @Test
    void missingResourceIsNotAssumed() {
        assertThat(capabilities.supportsResource("Coverage")).isFalse();
        assertThat(capabilities.supports("Coverage", FhirInteraction.READ)).isFalse();
        assertThat(capabilities.supportsResource(null)).isFalse();
        assertThat(capabilities.supportsResource(" ")).isFalse();
        assertThat(capabilities.resource("Coverage")).isEmpty();
    }

    @Test
    void declaredResourceDoesNotImplyEveryInteraction() {
        assertThat(capabilities.supportsResource("Patient")).isTrue();
        assertThat(capabilities.supports("Patient", FhirInteraction.CREATE)).isFalse();
        assertThat(capabilities.supports("Patient", FhirInteraction.UPDATE)).isFalse();
        assertThat(capabilities.supports("Patient", FhirInteraction.DELETE)).isFalse();
        assertThat(capabilities.supports("Observation", FhirInteraction.SEARCH_TYPE)).isFalse();
        assertThat(capabilities.supports("Patient", null)).isFalse();
    }
}
