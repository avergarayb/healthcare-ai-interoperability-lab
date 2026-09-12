package lab.healthcare.fhir.aihandoffauthorization;

import org.junit.jupiter.api.Test;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.stream.Stream;

import static org.assertj.core.api.Assertions.assertThat;

class AiHandoffAuthorizationArchitectureBoundaryTest {

    @Test
    void authorizationPackageDoesNotImportVendorsHapiOrModels() throws Exception {
        String text = sources(Path.of("src/main/java/lab/healthcare/fhir/aihandoffauthorization"));
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
        String boundary = Files.readString(
                Path.of("src/main/java/lab/healthcare/fhir/aihandoffauthorization/AiHandoffAuthorizationBoundary.java"));
        assertThat(boundary).doesNotContain("DeterministicAgent.evaluate");
        assertThat(boundary).doesNotContain("AgentStub.observe");
        assertThat(boundary).doesNotContain("FhirService");
        assertThat(boundary).doesNotContain("RestClient");
        assertThat(boundary).doesNotContain("WebClient");
        assertThat(boundary).doesNotContain("FirstAiComponent");
        assertThat(boundary).doesNotContain("AiExecutionGate");
        assertThat(boundary).doesNotContain("AiBoundaryService");
        String controller = Files.readString(Path.of(
                "src/main/java/lab/healthcare/fhir/aihandoffauthorization/web/AiHandoffAuthorizationController.java"));
        assertThat(controller).doesNotContain("RequestParam");
        assertThat(controller).doesNotContain("RequestHeader");
        assertThat(controller).doesNotContain("?authorized");
    }

    @Test
    void fhirServiceAndUpstreamLayersDoNotImportAuthorization() throws Exception {
        assertNoAuthorization(Path.of("src/main/java/lab/healthcare/fhir/client/FhirService.java"));
        assertNoAuthorization(Path.of("src/main/java/lab/healthcare/fhir/snapshot"));
        assertNoAuthorization(Path.of("src/main/java/lab/healthcare/fhir/projection"));
        assertNoAuthorization(Path.of("src/main/java/lab/healthcare/fhir/modelboundary"));
        assertNoAuthorization(Path.of("src/main/java/lab/healthcare/fhir/agentstub"));
        assertNoAuthorization(Path.of("src/main/java/lab/healthcare/fhir/pipeline"));
        assertNoAuthorization(Path.of("src/main/java/lab/healthcare/fhir/agent"));
        assertNoAuthorization(Path.of("src/main/java/lab/healthcare/fhir/aiboundary"));
        assertNoAuthorization(Path.of("src/main/java/lab/healthcare/fhir/firstai"));
        assertNoAuthorization(Path.of("src/main/java/lab/healthcare/fhir/aigateway"));
        assertNoAuthorization(Path.of("src/main/java/lab/healthcare/fhir/aiconsumer"));
        assertNoAuthorization(Path.of("src/main/java/lab/healthcare/fhir/aiconsumerpolicy"));
        assertNoAuthorization(Path.of("src/main/java/lab/healthcare/fhir/aiconsumerreadiness"));
    }

    private static void assertNoAuthorization(Path root) throws Exception {
        String text = Files.isRegularFile(root) ? Files.readString(root) : sources(root);
        assertThat(text).doesNotContain("lab.healthcare.fhir.aihandoffauthorization");
        assertThat(text).doesNotContain("AiHandoffAuthorization");
        assertThat(text).doesNotContain("HANDOFF_NOT_AUTHORIZED");
        assertThat(text).doesNotContain("REAL_AUTHORIZATION_NOT_IMPLEMENTED");
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
