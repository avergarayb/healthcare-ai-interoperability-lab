package lab.healthcare.fhir.pipeline;

import org.junit.jupiter.api.Test;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.stream.Stream;

import static org.assertj.core.api.Assertions.assertThat;

class PipelineArchitectureBoundaryTest {

    @Test
    void pipelinePackageDoesNotImportVendorsHapiOrFhirService() throws Exception {
        Path root = Path.of("src/main/java/lab/healthcare/fhir/pipeline");
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
        assertThat(text).doesNotContain("org.hl7.fhir");
        assertThat(text).doesNotContain("if Epic");
        assertThat(text).doesNotContain("if Oracle");
        assertThat(text).doesNotContain("EPIC_TIMEOUT");
        assertThat(text).doesNotContain("ORACLE_AUTH");
        assertThat(text).doesNotContain("https://");
        assertThat(text).doesNotContain("openai");
        assertThat(text).doesNotContain("lab.healthcare.fhir.agent.");
        assertThat(text).doesNotContain("DeterministicAgent");
    }

    @Test
    void fhirServiceAndUpstreamLayersDoNotImportPipeline() throws Exception {
        assertThat(Files.readString(Path.of("src/main/java/lab/healthcare/fhir/client/FhirService.java")))
                .doesNotContain("lab.healthcare.fhir.pipeline");
        assertNoPipelineImport(Path.of("src/main/java/lab/healthcare/fhir/snapshot"));
        assertNoPipelineImport(Path.of("src/main/java/lab/healthcare/fhir/projection"));
        assertNoPipelineImport(Path.of("src/main/java/lab/healthcare/fhir/modelboundary"));
        assertNoPipelineImport(Path.of("src/main/java/lab/healthcare/fhir/agentstub"));
    }

    private static void assertNoPipelineImport(Path root) throws Exception {
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
        assertThat(sources.toString()).doesNotContain("lab.healthcare.fhir.pipeline");
    }
}
