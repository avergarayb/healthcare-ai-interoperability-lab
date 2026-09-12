package lab.healthcare.fhir.firstai;

import org.junit.jupiter.api.Test;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.stream.Stream;

import static org.assertj.core.api.Assertions.assertThat;

class FirstAiArchitectureBoundaryTest {

    @Test
    void firstAiPackageDoesNotImportVendorsHapiOrModels() throws Exception {
        String text = sources(Path.of("src/main/java/lab/healthcare/fhir/firstai"));
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
        String mapper = Files.readString(Path.of("src/main/java/lab/healthcare/fhir/firstai/FirstAiMapper.java"));
        assertThat(mapper).doesNotContain("DeterministicAgent.evaluate");
        assertThat(mapper).doesNotContain("AgentStub.observe");
        assertThat(mapper).doesNotContain("FhirService");
        assertThat(mapper).doesNotContain("ModelBoundaryContract");
        String component = Files.readString(Path.of("src/main/java/lab/healthcare/fhir/firstai/FirstAiComponent.java"));
        assertThat(component).doesNotContain("DeterministicAgent.evaluate");
        assertThat(component).doesNotContain("AgentStub.observe");
        assertThat(component).doesNotContain("FhirService");
    }

    @Test
    void fhirServiceAndUpstreamLayersDoNotImportFirstAi() throws Exception {
        assertNoFirstAi(Path.of("src/main/java/lab/healthcare/fhir/client/FhirService.java"));
        assertNoFirstAi(Path.of("src/main/java/lab/healthcare/fhir/snapshot"));
        assertNoFirstAi(Path.of("src/main/java/lab/healthcare/fhir/projection"));
        assertNoFirstAi(Path.of("src/main/java/lab/healthcare/fhir/modelboundary"));
        assertNoFirstAi(Path.of("src/main/java/lab/healthcare/fhir/agentstub"));
        assertNoFirstAi(Path.of("src/main/java/lab/healthcare/fhir/pipeline"));
        assertNoFirstAi(Path.of("src/main/java/lab/healthcare/fhir/agent"));
        assertNoFirstAi(Path.of("src/main/java/lab/healthcare/fhir/aiboundary"));
    }

    private static void assertNoFirstAi(Path root) throws Exception {
        String text = Files.isRegularFile(root) ? Files.readString(root) : sources(root);
        assertThat(text).doesNotContain("lab.healthcare.fhir.firstai");
        assertThat(text).doesNotContain("FirstAiComponent");
        assertThat(text).doesNotContain("aiProcessingStatus");
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
