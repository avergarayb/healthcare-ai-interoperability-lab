package lab.healthcare.fhir.aiconsumerconsent;

import org.junit.jupiter.api.Test;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.stream.Stream;

import static org.assertj.core.api.Assertions.assertThat;

class AiConsumerConsentArchitectureBoundaryTest {

    @Test
    void coreDoesNotImportVendorsHapiOrUpstreamLayers() throws Exception {
        String core = sources(Path.of("src/main/java/lab/healthcare/fhir/aiconsumerconsent"), true);
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
        assertThat(core).doesNotContain("lab.healthcare.fhir.aihandoffauthorization");
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
                "src/main/java/lab/healthcare/fhir/aiconsumerconsent/AiConsumerConsentBoundary.java"));
        assertThat(boundary).doesNotContain("RestClient");
        assertThat(boundary).doesNotContain("WebClient");
        assertThat(boundary).doesNotContain("Feign");
        String controller = Files.readString(Path.of(
                "src/main/java/lab/healthcare/fhir/aiconsumerconsent/web/AiConsumerConsentController.java"));
        assertThat(controller).doesNotContain("RequestParam");
        assertThat(controller).doesNotContain("RequestHeader");
    }

    @Test
    void fhirServiceAndUpstreamLayersDoNotImportConsumerConsent() throws Exception {
        assertNoConsent(Path.of("src/main/java/lab/healthcare/fhir/client/FhirService.java"));
        assertNoConsent(Path.of("src/main/java/lab/healthcare/fhir/snapshot"));
        assertNoConsent(Path.of("src/main/java/lab/healthcare/fhir/projection"));
        assertNoConsent(Path.of("src/main/java/lab/healthcare/fhir/modelboundary"));
        assertNoConsent(Path.of("src/main/java/lab/healthcare/fhir/agentstub"));
        assertNoConsent(Path.of("src/main/java/lab/healthcare/fhir/pipeline"));
        assertNoConsent(Path.of("src/main/java/lab/healthcare/fhir/agent"));
        assertNoConsent(Path.of("src/main/java/lab/healthcare/fhir/aiboundary"));
        assertNoConsent(Path.of("src/main/java/lab/healthcare/fhir/firstai"));
        assertNoConsent(Path.of("src/main/java/lab/healthcare/fhir/aigateway"));
        assertNoConsent(Path.of("src/main/java/lab/healthcare/fhir/aiconsumer"));
        assertNoConsent(Path.of("src/main/java/lab/healthcare/fhir/aiconsumerpolicy"));
        assertNoConsent(Path.of("src/main/java/lab/healthcare/fhir/aiconsumerreadiness"));
        assertNoConsent(Path.of("src/main/java/lab/healthcare/fhir/aihandoffauthorization"));
        assertNoConsent(Path.of("src/main/java/lab/healthcare/fhir/aiconsumerauthorization"));
    }

    private static void assertNoConsent(Path root) throws Exception {
        String text = Files.isRegularFile(root) ? Files.readString(root) : sources(root, false);
        assertThat(text).doesNotContain("lab.healthcare.fhir.aiconsumerconsent");
        assertThat(text).doesNotContain("AiConsumerConsentBoundary");
        assertThat(text).doesNotContain("ConsumerConsentContext");
        assertThat(text).doesNotContain("UNTRUSTED_CONSENT_ASSERTION");
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
