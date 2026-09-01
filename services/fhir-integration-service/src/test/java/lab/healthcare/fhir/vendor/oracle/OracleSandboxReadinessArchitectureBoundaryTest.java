package lab.healthcare.fhir.vendor.oracle;

import org.junit.jupiter.api.Test;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.stream.Stream;

import static org.assertj.core.api.Assertions.assertThat;

class OracleSandboxReadinessArchitectureBoundaryTest {

    @Test
    void genericLayersDoNotContainOracleSandboxEnvOrReadiness() throws Exception {
        assertThat(Files.readString(Path.of("src/main/java/lab/healthcare/fhir/client/FhirService.java")))
                .doesNotContain("ORACLE_HEALTH_SANDBOX")
                .doesNotContain("OracleSandbox")
                .doesNotContain("lab.healthcare.fhir.vendor.oracle");
        assertThat(Files.readString(Path.of("src/main/java/lab/healthcare/fhir/routing/RoutingService.java")))
                .doesNotContain("ORACLE_HEALTH_SANDBOX")
                .doesNotContain("OracleSandbox")
                .doesNotContain("if (vendor");
        assertThat(Files.readString(Path.of("src/main/java/lab/healthcare/fhir/resilience/FhirRetryExecutor.java")))
                .doesNotContain("ORACLE_HEALTH")
                .doesNotContain("OracleSandbox");
        assertThat(Files.readString(Path.of("src/main/java/lab/healthcare/fhir/resilience/FhirCircuitBreaker.java")))
                .doesNotContain("ORACLE_HEALTH")
                .doesNotContain("client-id");
        assertThat(Files.readString(
                        Path.of("src/main/java/lab/healthcare/fhir/capability/FhirCapabilityDiscoveryService.java")))
                .doesNotContain("ORACLE_HEALTH")
                .doesNotContain("vendor.oracle");
        assertThat(Files.readString(Path.of("src/main/java/lab/healthcare/fhir/smart/SmartConfigurationClient.java")))
                .doesNotContain("ORACLE_HEALTH_SANDBOX")
                .doesNotContain("OracleSandbox");
    }

    @Test
    void connectivityPackageDoesNotImportOracleOrFhirService() throws Exception {
        Path root = Path.of("src/main/java/lab/healthcare/fhir/connectivity");
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
        assertThat(text).doesNotContain("FhirService");
        assertThat(text).doesNotContain("readPatient");
        assertThat(text).doesNotContain("ORACLE_HEALTH");
    }
}
