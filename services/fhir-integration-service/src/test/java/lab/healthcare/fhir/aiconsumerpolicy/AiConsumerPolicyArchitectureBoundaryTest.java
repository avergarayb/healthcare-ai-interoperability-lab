package lab.healthcare.fhir.aiconsumerpolicy;

import org.junit.jupiter.api.Test;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.stream.Stream;

import static org.assertj.core.api.Assertions.assertThat;

class AiConsumerPolicyArchitectureBoundaryTest {

    @Test
    void policyPackageDoesNotImportVendorsHapiOrModels() throws Exception {
        String text = sources(Path.of("src/main/java/lab/healthcare/fhir/aiconsumerpolicy"));
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
        String policy = Files.readString(Path.of("src/main/java/lab/healthcare/fhir/aiconsumerpolicy/AiConsumerPolicy.java"));
        assertThat(policy).doesNotContain("DeterministicAgent.evaluate");
        assertThat(policy).doesNotContain("AgentStub.observe");
        assertThat(policy).doesNotContain("FhirService");
        assertThat(policy).doesNotContain("RestClient");
        assertThat(policy).doesNotContain("WebClient");
    }

    @Test
    void fhirServiceAndUpstreamLayersDoNotImportPolicy() throws Exception {
        assertNoPolicy(Path.of("src/main/java/lab/healthcare/fhir/client/FhirService.java"));
        assertNoPolicy(Path.of("src/main/java/lab/healthcare/fhir/snapshot"));
        assertNoPolicy(Path.of("src/main/java/lab/healthcare/fhir/projection"));
        assertNoPolicy(Path.of("src/main/java/lab/healthcare/fhir/modelboundary"));
        assertNoPolicy(Path.of("src/main/java/lab/healthcare/fhir/agentstub"));
        assertNoPolicy(Path.of("src/main/java/lab/healthcare/fhir/pipeline"));
        assertNoPolicy(Path.of("src/main/java/lab/healthcare/fhir/agent"));
        assertNoPolicy(Path.of("src/main/java/lab/healthcare/fhir/aiboundary"));
        assertNoPolicy(Path.of("src/main/java/lab/healthcare/fhir/firstai"));
        assertNoPolicy(Path.of("src/main/java/lab/healthcare/fhir/aigateway"));
        assertNoPolicy(Path.of("src/main/java/lab/healthcare/fhir/aiconsumer"));
    }

    private static void assertNoPolicy(Path root) throws Exception {
        String text = Files.isRegularFile(root) ? Files.readString(root) : sources(root);
        assertThat(text).doesNotContain("lab.healthcare.fhir.aiconsumerpolicy");
        assertThat(text).doesNotContain("AiConsumerPolicy");
        assertThat(text).doesNotContain("ALLOWED_FOR_FUTURE_CONSUMPTION");
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
