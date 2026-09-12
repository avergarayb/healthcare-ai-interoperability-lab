package lab.healthcare.fhir.aiconsumeraccess;

import org.junit.jupiter.api.Test;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.stream.Stream;

import static org.assertj.core.api.Assertions.assertThat;

class AiConsumerClinicalDataAccessArchitectureBoundaryTest {

    @Test
    void coreDoesNotImportVendorsHapiOrUpstreamLayers() throws Exception {
        String core = sources(Path.of("src/main/java/lab/healthcare/fhir/aiconsumeraccess"), true);
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
        assertThat(core).doesNotContain("lab.healthcare.fhir.aiconsumerauthorization");
        assertThat(core).doesNotContain("lab.healthcare.fhir.aiconsumerconsent");
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
                "src/main/java/lab/healthcare/fhir/aiconsumeraccess/AiConsumerClinicalDataAccessBoundary.java"));
        assertThat(boundary).contains("lab.healthcare.fhir.aiconsumerscope.AiConsumerDataScopeResult");
        assertThat(boundary).doesNotContain("RestClient");
        assertThat(boundary).doesNotContain("WebClient");
        assertThat(boundary).doesNotContain("Feign");
        String controller = Files.readString(Path.of(
                "src/main/java/lab/healthcare/fhir/aiconsumeraccess/web/AiConsumerClinicalDataAccessController.java"));
        assertThat(controller).doesNotContain("RequestParam");
        assertThat(controller).doesNotContain("RequestHeader");
    }

    @Test
    void fhirServiceAndUpstreamLayersDoNotImportClinicalDataAccess() throws Exception {
        assertNoAccess(Path.of("src/main/java/lab/healthcare/fhir/client/FhirService.java"));
        assertNoAccess(Path.of("src/main/java/lab/healthcare/fhir/snapshot"));
        assertNoAccess(Path.of("src/main/java/lab/healthcare/fhir/projection"));
        assertNoAccess(Path.of("src/main/java/lab/healthcare/fhir/modelboundary"));
        assertNoAccess(Path.of("src/main/java/lab/healthcare/fhir/agentstub"));
        assertNoAccess(Path.of("src/main/java/lab/healthcare/fhir/pipeline"));
        assertNoAccess(Path.of("src/main/java/lab/healthcare/fhir/agent"));
        assertNoAccess(Path.of("src/main/java/lab/healthcare/fhir/aiboundary"));
        assertNoAccess(Path.of("src/main/java/lab/healthcare/fhir/firstai"));
        assertNoAccess(Path.of("src/main/java/lab/healthcare/fhir/aigateway"));
        assertNoAccess(Path.of("src/main/java/lab/healthcare/fhir/aiconsumer"));
        assertNoAccess(Path.of("src/main/java/lab/healthcare/fhir/aiconsumerpolicy"));
        assertNoAccess(Path.of("src/main/java/lab/healthcare/fhir/aiconsumerreadiness"));
        assertNoAccess(Path.of("src/main/java/lab/healthcare/fhir/aihandoffauthorization"));
        assertNoAccess(Path.of("src/main/java/lab/healthcare/fhir/aiconsumerauthorization"));
        assertNoAccess(Path.of("src/main/java/lab/healthcare/fhir/aiconsumerconsent"));
        assertNoAccess(Path.of("src/main/java/lab/healthcare/fhir/aiconsumerscope"));
    }

    private static void assertNoAccess(Path root) throws Exception {
        String text = Files.isRegularFile(root) ? Files.readString(root) : sources(root, false);
        assertThat(text).doesNotContain("lab.healthcare.fhir.aiconsumeraccess");
        assertThat(text).doesNotContain("AiConsumerClinicalDataAccessBoundary");
        assertThat(text).doesNotContain("ClinicalDataAccessRequestContext");
        assertThat(text).doesNotContain("UNTRUSTED_ACCESS_ASSERTION");
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
