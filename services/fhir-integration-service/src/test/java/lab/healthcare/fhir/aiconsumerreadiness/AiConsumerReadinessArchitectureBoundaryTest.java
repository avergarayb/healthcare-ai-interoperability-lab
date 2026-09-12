package lab.healthcare.fhir.aiconsumerreadiness;

import org.junit.jupiter.api.Test;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.stream.Stream;

import static org.assertj.core.api.Assertions.assertThat;

class AiConsumerReadinessArchitectureBoundaryTest {

    @Test
    void readinessPackageDoesNotImportVendorsHapiOrModels() throws Exception {
        String text = sources(Path.of("src/main/java/lab/healthcare/fhir/aiconsumerreadiness"));
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
        String readiness = Files.readString(
                Path.of("src/main/java/lab/healthcare/fhir/aiconsumerreadiness/AiConsumerReadiness.java"));
        assertThat(readiness).doesNotContain("DeterministicAgent.evaluate");
        assertThat(readiness).doesNotContain("AgentStub.observe");
        assertThat(readiness).doesNotContain("FhirService");
        assertThat(readiness).doesNotContain("RestClient");
        assertThat(readiness).doesNotContain("WebClient");
        assertThat(readiness).doesNotContain("FirstAiComponent");
        assertThat(readiness).doesNotContain("AiExecutionGate");
        assertThat(readiness).doesNotContain("AiBoundaryService");
    }

    @Test
    void fhirServiceAndUpstreamLayersDoNotImportReadiness() throws Exception {
        assertNoReadiness(Path.of("src/main/java/lab/healthcare/fhir/client/FhirService.java"));
        assertNoReadiness(Path.of("src/main/java/lab/healthcare/fhir/snapshot"));
        assertNoReadiness(Path.of("src/main/java/lab/healthcare/fhir/projection"));
        assertNoReadiness(Path.of("src/main/java/lab/healthcare/fhir/modelboundary"));
        assertNoReadiness(Path.of("src/main/java/lab/healthcare/fhir/agentstub"));
        assertNoReadiness(Path.of("src/main/java/lab/healthcare/fhir/pipeline"));
        assertNoReadiness(Path.of("src/main/java/lab/healthcare/fhir/agent"));
        assertNoReadiness(Path.of("src/main/java/lab/healthcare/fhir/aiboundary"));
        assertNoReadiness(Path.of("src/main/java/lab/healthcare/fhir/firstai"));
        assertNoReadiness(Path.of("src/main/java/lab/healthcare/fhir/aigateway"));
        assertNoReadiness(Path.of("src/main/java/lab/healthcare/fhir/aiconsumer"));
        assertNoReadiness(Path.of("src/main/java/lab/healthcare/fhir/aiconsumerpolicy"));
    }

    private static void assertNoReadiness(Path root) throws Exception {
        String text = Files.isRegularFile(root) ? Files.readString(root) : sources(root);
        assertThat(text).doesNotContain("lab.healthcare.fhir.aiconsumerreadiness");
        assertThat(text).doesNotContain("AiConsumerReadiness");
        assertThat(text).doesNotContain("READY_FOR_FUTURE_HANDOFF");
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
