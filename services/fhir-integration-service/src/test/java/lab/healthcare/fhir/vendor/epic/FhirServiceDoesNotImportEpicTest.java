package lab.healthcare.fhir.vendor.epic;

import org.junit.jupiter.api.Test;

import java.nio.file.Files;
import java.nio.file.Path;

import static org.assertj.core.api.Assertions.assertThat;

class FhirServiceDoesNotImportEpicTest {

    @Test
    void fhirServiceSourceDoesNotImportEpicVendorTypes() throws Exception {
        Path source = Path.of("src/main/java/lab/healthcare/fhir/client/FhirService.java");
        String contents = Files.readString(source);

        assertThat(contents).doesNotContain("lab.healthcare.fhir.vendor");
        assertThat(contents).doesNotContain("lab.healthcare.fhir.vendor.epic");
        assertThat(contents).doesNotContain("EpicIntegrationProfile");
        assertThat(contents).doesNotContain("Hyperspace");
        assertThat(contents).doesNotContain("fhir.epic.com");
    }
}
