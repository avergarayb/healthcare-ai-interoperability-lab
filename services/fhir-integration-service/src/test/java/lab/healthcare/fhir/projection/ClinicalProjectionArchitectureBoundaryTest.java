package lab.healthcare.fhir.projection;

import org.junit.jupiter.api.Test;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.stream.Stream;

import static org.assertj.core.api.Assertions.assertThat;

class ClinicalProjectionArchitectureBoundaryTest {

    @Test
    void projectionPackageDoesNotImportOracleOrHapiClients() throws Exception {
        Path root = Path.of("src/main/java/lab/healthcare/fhir/projection");
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
        assertThat(text).doesNotContain("OracleProjectionClient");
    }

    @Test
    void publicModelDoesNotExposeHapiResources() throws Exception {
        assertThat(source("RetainedPatient.java")).doesNotContain("org.hl7.fhir");
        assertThat(source("RetainedCondition.java")).doesNotContain("org.hl7.fhir");
        assertThat(source("RetainedObservation.java")).doesNotContain("org.hl7.fhir");
        assertThat(source("RetainedDiagnosticReport.java")).doesNotContain("org.hl7.fhir");
        assertThat(source("RetainedMedicationRequest.java")).doesNotContain("org.hl7.fhir");
        assertThat(source("ProjectedCollection.java")).doesNotContain("org.hl7.fhir");
        assertThat(source("ClinicalProjectionResult.java")).doesNotContain("org.hl7.fhir");
        assertThat(source("RetentionCeiling.java")).doesNotContain("org.hl7.fhir");
    }

    @Test
    void fhirServiceDoesNotImportProjection() throws Exception {
        String contents = Files.readString(Path.of("src/main/java/lab/healthcare/fhir/client/FhirService.java"));

        assertThat(contents).doesNotContain("lab.healthcare.fhir.projection");
        assertThat(contents).doesNotContain("ClinicalProjectionAssembler");
        assertThat(contents).doesNotContain("searchEverything");
        assertThat(contents).doesNotContain("lab.healthcare.fhir.vendor.oracle");
    }

    private static String source(String fileName) throws Exception {
        return Files.readString(Path.of("src/main/java/lab/healthcare/fhir/projection/" + fileName));
    }
}
