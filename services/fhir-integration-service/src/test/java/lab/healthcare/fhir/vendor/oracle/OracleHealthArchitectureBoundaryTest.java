package lab.healthcare.fhir.vendor.oracle;

import org.junit.jupiter.api.Test;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.stream.Stream;

import static org.assertj.core.api.Assertions.assertThat;

class OracleHealthArchitectureBoundaryTest {

    @Test
    void fhirServiceSourceDoesNotImportOracleVendorTypes() throws Exception {
        String contents = Files.readString(Path.of("src/main/java/lab/healthcare/fhir/client/FhirService.java"));

        assertThat(contents).doesNotContain("lab.healthcare.fhir.vendor.oracle");
        assertThat(contents).doesNotContain("OracleHealthIntegrationProfile");
        assertThat(contents).doesNotContain("OracleSandboxAuthenticationService");
        assertThat(contents).doesNotContain("OracleSandboxCapabilityDiscoveryService");
        assertThat(contents).doesNotContain("OracleSandboxAuthenticatedReadService");
        assertThat(contents).doesNotContain("OracleSandboxPatientContextService");
        assertThat(contents).doesNotContain("OracleSandboxConditionSearchService");
        assertThat(contents).doesNotContain("OracleSandboxObservationSearchService");
        assertThat(contents).doesNotContain("OracleSandboxDiagnosticReportSearchService");
        assertThat(contents).doesNotContain("OracleSandboxMedicationRequestSearchService");
        assertThat(contents).doesNotContain("OracleSandboxClinicalSnapshotService");
        assertThat(contents).doesNotContain("OracleSandboxClinicalProjectionService");
        assertThat(contents).doesNotContain("OracleSandboxModelBoundaryService");
        assertThat(contents).doesNotContain("lab.healthcare.fhir.patient");
        assertThat(contents).doesNotContain("lab.healthcare.fhir.snapshot");
        assertThat(contents).doesNotContain("lab.healthcare.fhir.projection");
        assertThat(contents).doesNotContain("lab.healthcare.fhir.modelboundary");
        assertThat(contents).doesNotContain("ORACLE_HEALTH");
    }

    @Test
    void routingAndResilienceDoNotSwitchOnOracleVendor() throws Exception {
        String routing = Files.readString(Path.of("src/main/java/lab/healthcare/fhir/routing/RoutingService.java"));
        String retry = Files.readString(Path.of("src/main/java/lab/healthcare/fhir/resilience/FhirRetryExecutor.java"));
        String circuit = Files.readString(
                Path.of("src/main/java/lab/healthcare/fhir/resilience/FhirCircuitBreaker.java"));

        assertThat(routing).doesNotContain("ORACLE_HEALTH");
        assertThat(retry).doesNotContain("ORACLE_HEALTH");
        assertThat(circuit).doesNotContain("ORACLE_HEALTH");
        assertThat(routing).doesNotContain("lab.healthcare.fhir.vendor.oracle");
    }

    @Test
    void oraclePackageDoesNotHardcodeVendorHostsOrHapiOperations() throws Exception {
        Path root = Path.of("src/main/java/lab/healthcare/fhir/vendor/oracle");
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
        assertThat(text).doesNotContain("https://");
        assertThat(text).doesNotContain("IGenericClient");
        assertThat(text).doesNotContain("new FhirService");
        assertThat(text).doesNotContain("OracleSmartConfigurationClient");
        assertThat(text).doesNotContain("OraclePkce");
        assertThat(text).doesNotContain("OracleTokenProvider");
        assertThat(text).doesNotContain("OracleCapabilityStatement");
        assertThat(text).doesNotContain("OracleCapabilityDiscoveryService");
        assertThat(text).doesNotContain("OraclePatientClient");
        assertThat(text).doesNotContain("OraclePatientReadClient");
        assertThat(text).doesNotContain("OracleConditionClient");
        assertThat(text).doesNotContain("OracleObservationClient");
        assertThat(text).doesNotContain("OracleDiagnosticReportClient");
        assertThat(text).doesNotContain("OracleMedicationRequestClient");
        assertThat(text).doesNotContain("OracleSnapshotClient");
        assertThat(text).doesNotContain("OracleProjectionClient");
        assertThat(text).doesNotContain("OracleModelBoundaryClient");
        assertThat(text).doesNotContain("OracleModelContext");
        assertThat(text).doesNotContain("OracleClinicalClient");
        assertThat(text).doesNotContain("cerner.com");
        assertThat(text).doesNotContain("authorization.cerner");
        assertThat(text).doesNotContain("lab-configured-patient");
    }
}
