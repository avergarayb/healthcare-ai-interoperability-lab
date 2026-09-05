package lab.healthcare.fhir.modelboundary;

import org.junit.jupiter.api.Test;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.stream.Stream;

import static org.assertj.core.api.Assertions.assertThat;

class ModelBoundaryArchitectureBoundaryTest {

    @Test
    void modelBoundaryPackageDoesNotImportVendorsHapiOrAi() throws Exception {
        Path root = Path.of("src/main/java/lab/healthcare/fhir/modelboundary");
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
        assertThat(text).doesNotContain("lab.healthcare.fhir.vendor.oracle");
        assertThat(text).doesNotContain("lab.healthcare.fhir.vendor.epic");
        assertThat(text).doesNotContain("ORACLE_HEALTH");
        assertThat(text).doesNotContain("IGenericClient");
        assertThat(text).doesNotContain("org.hl7.fhir");
        assertThat(text).doesNotContain("https://");
        assertThat(text).doesNotContain("cerner.com");
        assertThat(text).doesNotContain("openai");
        assertThat(text).doesNotContain("gemini");
        assertThat(text).doesNotContain("anthropic");
        assertThat(text).doesNotContain("OracleModelBoundaryClient");
        assertThat(text).doesNotContain("EpicModelBoundaryClient");
        assertThat(text).doesNotContain("OracleModelContext");
        assertThat(text).doesNotContain("EpicModelContext");
        assertThat(text).doesNotContain("OracleSandboxModelBoundaryService");
    }

    @Test
    void fhirServiceDoesNotImportModelBoundary() throws Exception {
        String contents = Files.readString(Path.of("src/main/java/lab/healthcare/fhir/client/FhirService.java"));

        assertThat(contents).doesNotContain("lab.healthcare.fhir.modelboundary");
        assertThat(contents).doesNotContain("ModelBoundaryMapper");
        assertThat(contents).doesNotContain("lab.healthcare.fhir.projection");
        assertThat(contents).doesNotContain("searchEverything");
    }
}
