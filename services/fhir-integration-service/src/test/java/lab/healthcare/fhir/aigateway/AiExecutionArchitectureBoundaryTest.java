package lab.healthcare.fhir.aigateway;

import org.junit.jupiter.api.Test;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.stream.Stream;

import static org.assertj.core.api.Assertions.assertThat;

class AiExecutionArchitectureBoundaryTest {

    @Test
    void executionGatePackageDoesNotImportVendorsHapiOrModels() throws Exception {
        String text = sources(Path.of("src/main/java/lab/healthcare/fhir/aigateway"));
        assertThat(text).doesNotContain("lab.healthcare.fhir.vendor.epic");
        assertThat(text).doesNotContain("lab.healthcare.fhir.vendor.oracle");
        assertThat(text).doesNotContain("lab.healthcare.fhir.client.FhirService");
        assertThat(text).doesNotContain("lab.healthcare.fhir.routing.RoutingService");
        assertThat(text).doesNotContain("lab.healthcare.fhir.projection");
        assertThat(text).doesNotContain("lab.healthcare.fhir.snapshot");
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
        String mapper = Files.readString(Path.of("src/main/java/lab/healthcare/fhir/aigateway/AiExecutionMapper.java"));
        assertThat(mapper).doesNotContain("DeterministicAgent.evaluate");
        assertThat(mapper).doesNotContain("AgentStub.observe");
        assertThat(mapper).doesNotContain("FhirService");
        assertThat(mapper).doesNotContain("ModelBoundaryContract");
        String gate = Files.readString(Path.of("src/main/java/lab/healthcare/fhir/aigateway/AiExecutionGate.java"));
        assertThat(gate).doesNotContain("DeterministicAgent.evaluate");
        assertThat(gate).doesNotContain("AgentStub.observe");
        assertThat(gate).doesNotContain("FhirService");
    }

    @Test
    void fhirServiceAndUpstreamLayersDoNotImportExecutionGate() throws Exception {
        assertNoExecutionGate(Path.of("src/main/java/lab/healthcare/fhir/client/FhirService.java"));
        assertNoExecutionGate(Path.of("src/main/java/lab/healthcare/fhir/snapshot"));
        assertNoExecutionGate(Path.of("src/main/java/lab/healthcare/fhir/projection"));
        assertNoExecutionGate(Path.of("src/main/java/lab/healthcare/fhir/modelboundary"));
        assertNoExecutionGate(Path.of("src/main/java/lab/healthcare/fhir/agentstub"));
        assertNoExecutionGate(Path.of("src/main/java/lab/healthcare/fhir/pipeline"));
        assertNoExecutionGate(Path.of("src/main/java/lab/healthcare/fhir/agent"));
        assertNoExecutionGate(Path.of("src/main/java/lab/healthcare/fhir/aiboundary"));
        assertNoExecutionGate(Path.of("src/main/java/lab/healthcare/fhir/firstai"));
    }

    private static void assertNoExecutionGate(Path root) throws Exception {
        String text = Files.isRegularFile(root) ? Files.readString(root) : sources(root);
        assertThat(text).doesNotContain("lab.healthcare.fhir.aigateway");
        assertThat(text).doesNotContain("AiExecutionGate");
        assertThat(text).doesNotContain("ELIGIBLE_BUT_NOT_AUTHORIZED");
    }

    private static String sources(Path root) throws Exception {
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
        return sources.toString();
    }
}
