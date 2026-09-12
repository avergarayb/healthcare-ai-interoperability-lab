package lab.healthcare.fhir.agent;

import org.junit.jupiter.api.Test;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.stream.Stream;

import static org.assertj.core.api.Assertions.assertThat;

class DeterministicAgentArchitectureBoundaryTest {

    @Test
    void agentPackageDoesNotImportVendorsHapiOrFhirService() throws Exception {
        Path root = Path.of("src/main/java/lab/healthcare/fhir/agent");
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
        assertThat(text).doesNotContain("lab.healthcare.fhir.vendor.epic");
        assertThat(text).doesNotContain("lab.healthcare.fhir.vendor.oracle");
        assertThat(text).doesNotContain("lab.healthcare.fhir.client.FhirService");
        assertThat(text).doesNotContain("lab.healthcare.fhir.routing.RoutingService");
        assertThat(text).doesNotContain("lab.healthcare.fhir.projection");
        assertThat(text).doesNotContain("org.hl7.fhir");
        assertThat(text).doesNotContain("IGenericClient");
        assertThat(text).doesNotContain("openai");
        assertThat(text).doesNotContain("gemini");
        assertThat(text).doesNotContain("anthropic");
        assertThat(text).doesNotContain("langchain");
        assertThat(text).doesNotContain("langgraph");
        assertThat(text).doesNotContain("https://");
        assertThat(text).doesNotContain("if Epic");
        assertThat(text).doesNotContain("if Oracle");
        assertThat(text).doesNotContain("EpicAgent");
        assertThat(text).doesNotContain("OracleAgent");
        String agent = Files.readString(Path.of("src/main/java/lab/healthcare/fhir/agent/DeterministicAgent.java"));
        assertThat(agent).doesNotContain("lab.healthcare.fhir.smart");
        assertThat(agent).doesNotContain("FhirService");
        assertThat(agent).doesNotContain("RoutingService");
    }

    @Test
    void fhirServiceAndUpstreamLayersDoNotImportAgent() throws Exception {
        assertNoAgentImport(Path.of("src/main/java/lab/healthcare/fhir/client/FhirService.java"));
        assertNoAgentImport(Path.of("src/main/java/lab/healthcare/fhir/snapshot"));
        assertNoAgentImport(Path.of("src/main/java/lab/healthcare/fhir/projection"));
        assertNoAgentImport(Path.of("src/main/java/lab/healthcare/fhir/modelboundary"));
        assertNoAgentImport(Path.of("src/main/java/lab/healthcare/fhir/agentstub"));
        assertNoAgentImport(Path.of("src/main/java/lab/healthcare/fhir/pipeline"));
    }

    private static void assertNoAgentImport(Path root) throws Exception {
        StringBuilder sources = new StringBuilder();
        if (Files.isRegularFile(root)) {
            sources.append(Files.readString(root));
        } else {
            try (Stream<Path> files = Files.walk(root)) {
                files.filter(path -> path.toString().endsWith(".java")).forEach(path -> {
                    try {
                        sources.append(Files.readString(path));
                    } catch (Exception ex) {
                        throw new IllegalStateException(path.toString(), ex);
                    }
                });
            }
        }
        String text = sources.toString();
        assertThat(text).doesNotContain("lab.healthcare.fhir.agent.");
        assertThat(text).doesNotContain("package lab.healthcare.fhir.agent;");
    }
}
