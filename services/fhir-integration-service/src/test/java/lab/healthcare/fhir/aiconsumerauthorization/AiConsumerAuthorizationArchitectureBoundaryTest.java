package lab.healthcare.fhir.aiconsumerauthorization;

import org.junit.jupiter.api.Test;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.stream.Stream;

import static org.assertj.core.api.Assertions.assertThat;

class AiConsumerAuthorizationArchitectureBoundaryTest {

    @Test
    void coreDoesNotImportVendorsHapiOrUpstreamLayers() throws Exception {
        String core = sources(Path.of("src/main/java/lab/healthcare/fhir/aiconsumerauthorization"), true);
        assertThat(core).doesNotContain("lab.healthcare.fhir.vendor.epic");
        assertThat(core).doesNotContain("lab.healthcare.fhir.vendor.oracle");
        assertThat(core).doesNotContain("lab.healthcare.fhir.client.FhirService");
        assertThat(core).doesNotContain("lab.healthcare.fhir.routing.RoutingService");
        assertThat(core).doesNotContain("lab.healthcare.fhir.projection");
        assertThat(core).doesNotContain("lab.healthcare.fhir.snapshot");
        assertThat(core).doesNotContain("lab.healthcare.fhir.pipeline");
        assertThat(core).doesNotContain("lab.healthcare.fhir.agent");
        assertThat(core).doesNotContain("lab.healthcare.fhir.aiboundary");
        assertThat(core).doesNotContain("lab.healthcare.fhir.firstai");
        assertThat(core).doesNotContain("lab.healthcare.fhir.aigateway");
        assertThat(core).doesNotContain("lab.healthcare.fhir.aiconsumerpolicy");
        assertThat(core).doesNotContain("lab.healthcare.fhir.aiconsumerreadiness");
        assertThat(core).doesNotContain("lab.healthcare.fhir.aiconsumer.");
        assertThat(core).doesNotContain("org.hl7.fhir");
        assertThat(core).doesNotContain("IGenericClient");
        assertThat(core).doesNotContain("openai");
        assertThat(core).doesNotContain("gemini");
        assertThat(core).doesNotContain("anthropic");
        assertThat(core).doesNotContain("langchain");
        assertThat(core).doesNotContain("langgraph");
        assertThat(core).doesNotContain("https://");
        assertThat(core).doesNotContain("if Epic");
        assertThat(core).doesNotContain("if Oracle");
        String boundary = Files.readString(Path.of(
                "src/main/java/lab/healthcare/fhir/aiconsumerauthorization/AiConsumerAuthorizationBoundary.java"));
        assertThat(boundary).doesNotContain("RestClient");
        assertThat(boundary).doesNotContain("WebClient");
        assertThat(boundary).doesNotContain("Feign");
        String controller = Files.readString(Path.of(
                "src/main/java/lab/healthcare/fhir/aiconsumerauthorization/web/AiConsumerAuthorizationController.java"));
        assertThat(controller).doesNotContain("RequestParam");
        assertThat(controller).doesNotContain("RequestHeader");
    }

    @Test
    void fhirServiceAndUpstreamLayersDoNotImportConsumerAuthorization() throws Exception {
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
        assertNoAuthorization(Path.of("src/main/java/lab/healthcare/fhir/aihandoffauthorization"));
    }

    private static void assertNoAuthorization(Path root) throws Exception {
        String text = Files.isRegularFile(root) ? Files.readString(root) : sources(root, false);
        assertThat(text).doesNotContain("lab.healthcare.fhir.aiconsumerauthorization");
        assertThat(text).doesNotContain("AiConsumerAuthorizationBoundary");
        assertThat(text).doesNotContain("ConsumerSecurityContext");
        assertThat(text).doesNotContain("UNTRUSTED_AUTHENTICATION_ASSERTION");
    }

    private static String sources(Path root, boolean coreOnly) throws Exception {
        StringBuilder sources = new StringBuilder();
        try (Stream<Path> files = Files.walk(root)) {
            files.filter(path -> path.toString().endsWith(".java"))
                    .filter(path -> !coreOnly || !isWeb(path))
                    .forEach(path -> {
                        try {
                            sources.append(Files.readString(path));
                        } catch (Exception ex) {
                            throw new IllegalStateException(path.toString(), ex);
                        }
                    });
        }
        return sources.toString();
    }

    private static boolean isWeb(Path path) {
        String value = path.toString().replace('\\', '/');
        return value.contains("/web/");
    }
}
