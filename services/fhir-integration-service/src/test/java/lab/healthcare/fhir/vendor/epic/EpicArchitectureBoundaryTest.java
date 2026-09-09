package lab.healthcare.fhir.vendor.epic;

import org.junit.jupiter.api.Test;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.stream.Stream;

import static org.assertj.core.api.Assertions.assertThat;

class EpicArchitectureBoundaryTest {

    @Test
    void fhirServiceSourceDoesNotImportEpicVendorTypes() throws Exception {
        String contents = Files.readString(Path.of("src/main/java/lab/healthcare/fhir/client/FhirService.java"));

        assertThat(contents).doesNotContain("lab.healthcare.fhir.vendor.epic");
        assertThat(contents).doesNotContain("EpicIntegrationProfile");
        assertThat(contents).doesNotContain("EpicSandboxAuthenticationService");
        assertThat(contents).doesNotContain("EPIC_SANDBOX");
    }

    @Test
    void routingAndResilienceDoNotSwitchOnEpicVendor() throws Exception {
        String routing = Files.readString(Path.of("src/main/java/lab/healthcare/fhir/routing/RoutingService.java"));
        String retry = Files.readString(Path.of("src/main/java/lab/healthcare/fhir/resilience/FhirRetryExecutor.java"));
        String circuit = Files.readString(Path.of("src/main/java/lab/healthcare/fhir/resilience/FhirCircuitBreaker.java"));
        String factory = Files.readString(Path.of("src/main/java/lab/healthcare/fhir/client/FhirClientFactory.java"));

        assertThat(routing).doesNotContain("if Epic");
        assertThat(routing).doesNotContain("FhirVendor.EPIC");
        assertThat(retry).doesNotContain("FhirVendor.EPIC");
        assertThat(circuit).doesNotContain("FhirVendor.EPIC");
        assertThat(factory).doesNotContain("FhirVendor.EPIC");
        assertThat(routing).doesNotContain("lab.healthcare.fhir.vendor.epic");
    }

    @Test
    void epicPackageDoesNotAddVendorClientsOrHardcodedOauthHosts() throws Exception {
        Path root = Path.of("src/main/java/lab/healthcare/fhir/vendor/epic");
        StringBuilder sources = new StringBuilder();
        try (Stream<Path> files = Files.walk(root)) {
            files.filter(path -> path.toString().endsWith(".java"))
                    .filter(path -> !path.getFileName().toString().equals("EpicSandboxEndpoints.java"))
                    .forEach(path -> {
                        try {
                            sources.append(Files.readString(path));
                        } catch (Exception ex) {
                            throw new IllegalStateException(path.toString(), ex);
                        }
                    });
        }
        String text = sources.toString();
        assertThat(text).doesNotContain("https://");
        assertThat(text).doesNotContain("fhir.epic.com");
        assertThat(text).doesNotContain("IGenericClient");
        assertThat(text).doesNotContain("new FhirService");
        assertThat(text).doesNotContain("class EpicClient");
        assertThat(text).doesNotContain("EpicSmartClient");
        assertThat(text).doesNotContain("EpicPatientClient");
        assertThat(text).doesNotContain("EpicOAuthClient");
        assertThat(text).doesNotContain("EpicPkce");
        assertThat(text).doesNotContain("EpicTokenProvider");
        assertThat(text).doesNotContain("discoverCapabilities(\"epic-sandbox\")");
        assertThat(text).doesNotContain("EpicCapabilityStatement");
        assertThat(text).doesNotContain("EpicPatientClient");
        assertThat(text).doesNotContain("EpicPatientContext");
        assertThat(text).doesNotContain("org.hl7.fhir.r4.model.CapabilityStatement");
        assertThat(text).doesNotContain("org.hl7.fhir.r4.model.Patient");
        assertThat(text).doesNotContain("searchPatients");
    }
}
