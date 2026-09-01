package lab.healthcare.fhir.capability;

import org.junit.jupiter.api.Test;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.stream.Stream;

import static org.assertj.core.api.Assertions.assertThat;

class FhirCapabilityArchitectureBoundaryTest {

    @Test
    void fhirServiceDoesNotImportCapabilityOrVendorPackages() throws Exception {
        String contents = Files.readString(Path.of("src/main/java/lab/healthcare/fhir/client/FhirService.java"));

        assertThat(contents).doesNotContain("lab.healthcare.fhir.capability");
        assertThat(contents).doesNotContain("lab.healthcare.fhir.vendor");
        assertThat(contents).doesNotContain("EPIC");
        assertThat(contents).doesNotContain("ORACLE_HEALTH");
        assertThat(contents).doesNotContain("FhirServerCapabilities");
    }

    @Test
    void routingAndResilienceDoNotSwitchOnVendorForDiscovery() throws Exception {
        String routing = Files.readString(Path.of("src/main/java/lab/healthcare/fhir/routing/RoutingService.java"));
        String retry = Files.readString(Path.of("src/main/java/lab/healthcare/fhir/resilience/FhirRetryExecutor.java"));
        String circuit = Files.readString(
                Path.of("src/main/java/lab/healthcare/fhir/resilience/FhirCircuitBreaker.java"));

        assertThat(routing).doesNotContain("FhirVendor.EPIC");
        assertThat(routing).doesNotContain("ORACLE_HEALTH");
        assertThat(routing).doesNotContain("if (vendor");
        assertThat(retry).doesNotContain("EPIC");
        assertThat(retry).doesNotContain("ORACLE_HEALTH");
        assertThat(circuit).doesNotContain("EPIC");
        assertThat(circuit).doesNotContain("ORACLE_HEALTH");
        assertThat(retry).doesNotContain("lab.healthcare.fhir.capability");
        assertThat(circuit).doesNotContain("lab.healthcare.fhir.capability");
    }

    @Test
    void capabilityPackageDoesNotImportVendorsOrCache() throws Exception {
        Path root = Path.of("src/main/java/lab/healthcare/fhir/capability");
        StringBuilder sources = new StringBuilder();
        try (Stream<Path> files = Files.walk(root)) {
            files.filter(path -> path.toString().endsWith(".java")).forEach(path -> {
                try {
                    sources.append(Files.readString(path));
                } catch (Exception ex) {
                    throw new IllegalStateException(path.toString(), ex);
                }
            });
        }
        String text = sources.toString();
        assertThat(text).doesNotContain("lab.healthcare.fhir.vendor");
        assertThat(text).doesNotContain("EPIC");
        assertThat(text).doesNotContain("ORACLE_HEALTH");
        assertThat(text).doesNotContain("Redis");
        assertThat(text).doesNotContain("Cache");
        assertThat(text).doesNotContain("createPatient");
    }
}
