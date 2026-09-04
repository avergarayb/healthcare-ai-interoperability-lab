package lab.healthcare.fhir.snapshot;

import org.junit.jupiter.api.Test;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.stream.Stream;

import static org.assertj.core.api.Assertions.assertThat;

class ClinicalSnapshotArchitectureBoundaryTest {

    @Test
    void snapshotPackageDoesNotImportOracleOrHapiClients() throws Exception {
        Path root = Path.of("src/main/java/lab/healthcare/fhir/snapshot");
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
        assertThat(text).doesNotContain("ORACLE_HEALTH");
        assertThat(text).doesNotContain("IGenericClient");
        assertThat(text).doesNotContain("https://");
        assertThat(text).doesNotContain("cerner.com");
    }

    @Test
    void fhirServiceDoesNotImportSnapshot() throws Exception {
        String contents = Files.readString(Path.of("src/main/java/lab/healthcare/fhir/client/FhirService.java"));

        assertThat(contents).doesNotContain("lab.healthcare.fhir.snapshot");
        assertThat(contents).doesNotContain("ClinicalSnapshotAssembler");
        assertThat(contents).doesNotContain("searchEverything");
    }
}
