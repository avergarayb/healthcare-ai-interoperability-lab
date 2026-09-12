package lab.healthcare.fhir.agentstub;

import org.junit.jupiter.api.Test;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.stream.Stream;

import static org.assertj.core.api.Assertions.assertThat;

class AgentStubArchitectureBoundaryTest {

    @Test
    void agentStubPackageDoesNotImportVendorsHapiOrModels() throws Exception {
        Path root = Path.of("src/main/java/lab/healthcare/fhir/agentstub");
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
        assertThat(text).doesNotContain("lab.healthcare.fhir.projection");
        assertThat(text).doesNotContain("lab.healthcare.fhir.routing");
        assertThat(text).doesNotContain("lab.healthcare.fhir.client.FhirService");
        assertThat(text).doesNotContain("IGenericClient");
        assertThat(text).doesNotContain("org.hl7.fhir");
        assertThat(text).doesNotContain("openai");
        assertThat(text).doesNotContain("gemini");
        assertThat(text).doesNotContain("anthropic");
        assertThat(text).doesNotContain("https://");
        assertThat(text).doesNotContain("EpicAgentStub");
        assertThat(text).doesNotContain("OracleAgentStub");
        assertThat(text).doesNotContain("EpicAgentService");
        assertThat(text).doesNotContain("OracleAgentService");
        assertThat(text).doesNotContain("if Epic");
        assertThat(text).doesNotContain("if Oracle");
        String stub = Files.readString(Path.of("src/main/java/lab/healthcare/fhir/agentstub/AgentStub.java"));
        assertThat(stub).doesNotContain("lab.healthcare.fhir.smart");
        assertThat(stub).doesNotContain("FhirService");
        assertThat(stub).doesNotContain("RoutingService");
    }

    @Test
    void fhirServiceDoesNotImportAgentStub() throws Exception {
        String contents = Files.readString(Path.of("src/main/java/lab/healthcare/fhir/client/FhirService.java"));

        assertThat(contents).doesNotContain("lab.healthcare.fhir.agentstub");
        assertThat(contents).doesNotContain("AgentStub");
        assertThat(contents).doesNotContain("searchEverything");
    }
}
