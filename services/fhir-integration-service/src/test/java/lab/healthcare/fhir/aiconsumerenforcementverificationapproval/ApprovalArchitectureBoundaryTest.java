package lab.healthcare.fhir.aiconsumerenforcementverificationapproval;

import org.junit.jupiter.api.Test;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.stream.Stream;

import static org.assertj.core.api.Assertions.assertThat;

class ApprovalArchitectureBoundaryTest {

    @Test
    void coreDoesNotImportVendorsHapiOrUpstreamLayers() throws Exception {
        String core = sources(
                Path.of("src/main/java/lab/healthcare/fhir/aiconsumerenforcementverificationapproval"), true);
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
        assertThat(core).doesNotContain("lab.healthcare.fhir.aiconsumerscope");
        assertThat(core).doesNotContain("lab.healthcare.fhir.aiconsumeraccess");
        assertThat(core).doesNotContain("lab.healthcare.fhir.aiconsumerenforcement.");
        assertThat(core).doesNotContain("lab.healthcare.fhir.aiconsumerenforcementexecution");
        assertThat(core).doesNotContain("lab.healthcare.fhir.aiconsumer.");
        assertThat(core).doesNotContain("org.hl7.fhir");
        assertThat(core).doesNotContain("openai");
        assertThat(core).doesNotContain("WebClient");
        assertThat(core).doesNotContain("RestClient");
        assertThat(core).doesNotContain("RestTemplate");
        assertThat(core).doesNotContain("Evaluator");
        String boundary = Files.readString(Path.of(
                "src/main/java/lab/healthcare/fhir/aiconsumerenforcementverificationapproval/"
                        + "AiConsumerEnforcementVerificationApprovalBoundary.java"));
        assertThat(boundary).contains(
                "lab.healthcare.fhir.aiconsumerenforcementverificationdecision.AiConsumerVerificationDecisionResult");
        assertThat(boundary).contains("class AiConsumerEnforcementVerificationApprovalBoundary");
        String controller = Files.readString(Path.of(
                "src/main/java/lab/healthcare/fhir/aiconsumerenforcementverificationapproval/web/"
                        + "AiConsumerEnforcementVerificationApprovalController.java"));
        assertThat(controller).doesNotContain("RequestParam");
        assertThat(controller).doesNotContain("RequestHeader");
    }

    @Test
    void fhirServiceAndUpstreamLayersDoNotImportApproval() throws Exception {
        assertNoApproval(Path.of("src/main/java/lab/healthcare/fhir/client/FhirService.java"));
        assertNoApproval(Path.of("src/main/java/lab/healthcare/fhir/aiconsumerenforcementverificationdecision"));
        assertNoApproval(Path.of("src/main/java/lab/healthcare/fhir/aiconsumerenforcementverification"));
        assertNoApproval(Path.of("src/main/java/lab/healthcare/fhir/aiconsumerenforcementexecution"));
        assertNoApproval(Path.of("src/main/java/lab/healthcare/fhir/aiconsumerenforcement"));
        assertNoApproval(Path.of("src/main/java/lab/healthcare/fhir/modelboundary"));
    }

    private static void assertNoApproval(Path root) throws Exception {
        String text = Files.isRegularFile(root) ? Files.readString(root) : sources(root, false);
        assertThat(text).doesNotContain("lab.healthcare.fhir.aiconsumerenforcementverificationapproval");
        assertThat(text).doesNotContain("AiConsumerEnforcementVerificationApprovalBoundary");
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
        return path.toString().replace('\\', '/').contains("/web/");
    }
}
