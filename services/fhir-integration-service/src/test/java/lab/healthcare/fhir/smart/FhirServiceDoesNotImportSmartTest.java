package lab.healthcare.fhir.smart;

import org.junit.jupiter.api.Test;

import java.nio.file.Files;
import java.nio.file.Path;

import static org.assertj.core.api.Assertions.assertThat;

class FhirServiceDoesNotImportSmartTest {

    @Test
    void fhirServiceSourceDoesNotImportSmartTypes() throws Exception {
        Path source = Path.of("src/main/java/lab/healthcare/fhir/client/FhirService.java");
        String contents = Files.readString(source);

        assertThat(contents).doesNotContain("lab.healthcare.fhir.smart");
        assertThat(contents).doesNotContain("SmartCapabilities");
        assertThat(contents).doesNotContain("SmartConfigurationValidator");
        assertThat(contents).doesNotContain("SmartAuthorizationRequest");
    }
}
