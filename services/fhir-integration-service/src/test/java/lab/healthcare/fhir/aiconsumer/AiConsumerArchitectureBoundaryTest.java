package lab.healthcare.fhir.aiconsumer;

import org.junit.jupiter.api.Test;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.stream.Stream;

import static org.assertj.core.api.Assertions.assertThat;

class AiConsumerArchitectureBoundaryTest {

    @Test
    void consumerPackageDoesNotImportVendorsHapiOrModels() throws Exception {
        String text = sources(Path.of("src/main/java/lab/healthcare/fhir/aiconsumer"));
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
        String mapper = Files.readString(Path.of("src/main/java/lab/healthcare/fhir/aiconsumer/AiConsumerContractMapper.java"));
        assertThat(mapper).doesNotContain("DeterministicAgent.evaluate");
        assertThat(mapper).doesNotContain("AgentStub.observe");
        assertThat(mapper).doesNotContain("FhirService");
        assertThat(mapper).doesNotContain("RestClient");
        assertThat(mapper).doesNotContain("WebClient");
        String service = Files.readString(Path.of("src/main/java/lab/healthcare/fhir/aiconsumer/AiConsumerContractService.java"));
        assertThat(service).doesNotContain("DeterministicAgent.evaluate");
        assertThat(service).doesNotContain("AgentStub.observe");
        assertThat(service).doesNotContain("FhirService");
        assertThat(service).doesNotContain("RestClient");
    }

    @Test
    void fhirServiceAndUpstreamLayersDoNotImportConsumerContract() throws Exception {
        assertNoConsumer(Path.of("src/main/java/lab/healthcare/fhir/client/FhirService.java"));
        assertNoConsumer(Path.of("src/main/java/lab/healthcare/fhir/snapshot"));
        assertNoConsumer(Path.of("src/main/java/lab/healthcare/fhir/projection"));
        assertNoConsumer(Path.of("src/main/java/lab/healthcare/fhir/modelboundary"));
        assertNoConsumer(Path.of("src/main/java/lab/healthcare/fhir/agentstub"));
        assertNoConsumer(Path.of("src/main/java/lab/healthcare/fhir/pipeline"));
        assertNoConsumer(Path.of("src/main/java/lab/healthcare/fhir/agent"));
        assertNoConsumer(Path.of("src/main/java/lab/healthcare/fhir/aiboundary"));
        assertNoConsumer(Path.of("src/main/java/lab/healthcare/fhir/firstai"));
        assertNoConsumer(Path.of("src/main/java/lab/healthcare/fhir/aigateway"));
    }

    private static void assertNoConsumer(Path root) throws Exception {
        String text = Files.isRegularFile(root) ? Files.readString(root) : sources(root);
        assertThat(text).doesNotContain("lab.healthcare.fhir.aiconsumer");
        assertThat(text).doesNotContain("AiConsumerContract");
        assertThat(text).doesNotContain("NOT_DISPATCHED");
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
